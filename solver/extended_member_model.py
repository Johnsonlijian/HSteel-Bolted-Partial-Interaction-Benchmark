"""Extended pure-Python reduced-order solver for the W3c toy benchmark.

The model is intentionally small and auditable. It uses Euler-Bernoulli beam
segments for the built-up member, updates an effective flexural stiffness from
the current bolt-row stick/slip states, includes a linearized P-Delta geometric
stiffness, and drives the imported interface laws at each bolt row. It is not a
commercial finite-element replacement; it is the reproducible medium-fidelity
kernel used for the Path-C manuscript evidence chain.
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from solver.interface_law import BoltPreloadRelaxation, PressureIndexedStickSlip
from solver.reduced_member_model import cyclic_displacement_history


HISTORY_COLUMNS = [
    "step",
    "time_or_drift",
    "applied_displacement",
    "base_reaction",
    "row_idx",
    "row_slip",
    "row_connector_force",
    "row_dissipation_increment",
    "row_q_b",
    "row_sticking_flag",
]


@dataclass(frozen=True)
class RelaxationCalibration:
    eta_dis: float
    q_b_residual: float


@dataclass(frozen=True)
class SectionProperties:
    area_single: float
    i_single: float
    i_sep: float
    i_mono: float
    ei_sep: float
    ei_mono: float


@dataclass(frozen=True)
class ExtendedMemberConfig:
    length: float = 3000.0
    n_segments: int = 10
    n_bolt_rows: int = 3
    h: float = 100.0
    b: float = 100.0
    t1: float = 6.0
    t2: float = 8.0
    elastic_modulus: float = 206_000.0
    axial_ratio: float = 0.25
    p_delta_active: bool = True
    mu: float = 0.35
    k_stick: float = 0.35
    q_b0: float = 1.0
    eta_dis: float | None = None
    q_b_residual: float | None = None
    slip_scale: float = 0.018
    row_shape_profile: str = "outer_amplified"
    max_drift: float = 0.04
    points_per_branch: int = 30
    newton_tol: float = 1e-6
    max_newton_iterations: int = 50

    def __post_init__(self) -> None:
        if self.n_segments < 1:
            raise ValueError("n_segments must be positive")
        if self.n_bolt_rows < 1:
            raise ValueError("n_bolt_rows must be positive")
        if self.length <= 0:
            raise ValueError("length must be positive")
        if self.elastic_modulus <= 0:
            raise ValueError("elastic_modulus must be positive")
        if self.max_newton_iterations < 1:
            raise ValueError("max_newton_iterations must be positive")


@dataclass
class StepState:
    displacements: np.ndarray
    reaction: float
    row_slips: list[float]
    row_forces: list[float]
    row_dissipation_increments: list[float]
    row_q_b: list[float]
    row_sticking: list[bool]
    composite_factor: float
    newton_iterations: int
    converged: bool
    residual_norm: float


def default_fit_table() -> Path:
    env_value = os.environ.get("HSTEEL_OUTPUT_DIR")
    if env_value:
        path = Path(env_value)
        output_dir = path if path.is_absolute() else PROJECT_ROOT / path
        return output_dir / "relaxation_fit_table.csv"
    public_outputs = PROJECT_ROOT / "outputs"
    if public_outputs.exists() and not (PROJECT_ROOT / "rounds").exists():
        return public_outputs / "relaxation_fit_table.csv"
    return PROJECT_ROOT / "rounds" / "R06_path2_opensees_benchmark" / "outputs" / "relaxation_fit_table.csv"


def load_ds1_calibration(fit_table: Path) -> RelaxationCalibration:
    """Read the W2 ds1 steel-bolt calibration row at runtime."""

    with fit_table.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["dataset_id"] == "ds1_eraliev2021_m12_120c":
                return RelaxationCalibration(
                    eta_dis=float(row["eta_dis"]),
                    q_b_residual=float(row["q_b_residual"]),
                )
    raise ValueError(f"ds1 calibration row not found in {fit_table}")


def h_section_properties(config: ExtendedMemberConfig) -> SectionProperties:
    """Return full-height H-section properties consistent with W3b geometry."""

    web_height = config.h - 2.0 * config.t2
    area_single = 2.0 * config.b * config.t2 + web_height * config.t1
    i_single = (
        config.b * config.h**3
        - (config.b - config.t1) * max(web_height, 0.0) ** 3
    ) / 12.0
    i_sep = 2.0 * i_single
    separation = config.h
    i_mono = i_sep + area_single * separation**2 / 2.0
    return SectionProperties(
        area_single=area_single,
        i_single=i_single,
        i_sep=i_sep,
        i_mono=i_mono,
        ei_sep=config.elastic_modulus * i_sep,
        ei_mono=config.elastic_modulus * i_mono,
    )


def bolt_row_positions(config: ExtendedMemberConfig) -> np.ndarray:
    return np.linspace(
        config.length / (config.n_bolt_rows + 1),
        config.length * config.n_bolt_rows / (config.n_bolt_rows + 1),
        config.n_bolt_rows,
    )


def row_shape_factors(n_bolt_rows: int, profile: str = "outer_amplified") -> np.ndarray:
    if n_bolt_rows == 1:
        return np.ones(1, dtype=float)
    x = np.linspace(-1.0, 1.0, n_bolt_rows)
    if profile == "outer_amplified":
        return 0.35 + 0.65 * np.abs(x)
    if profile == "uniform":
        return np.ones(n_bolt_rows, dtype=float)
    if profile == "outer_mild":
        return 0.75 + 0.25 * np.abs(x)
    if profile == "center_amplified":
        return 0.35 + 0.65 * (1.0 - np.abs(x))
    raise ValueError(
        "unknown row_shape_profile; expected one of "
        "outer_amplified, uniform, outer_mild, center_amplified"
    )


def _beam_stiffness(ei: float, length: float) -> np.ndarray:
    l = length
    return (ei / l**3) * np.asarray(
        [
            [12.0, 6.0 * l, -12.0, 6.0 * l],
            [6.0 * l, 4.0 * l**2, -6.0 * l, 2.0 * l**2],
            [-12.0, -6.0 * l, 12.0, -6.0 * l],
            [6.0 * l, 2.0 * l**2, -6.0 * l, 4.0 * l**2],
        ],
        dtype=float,
    )


def _geometric_stiffness(axial_load: float, length: float) -> np.ndarray:
    """Consistent beam-column geometric stiffness for a compressive axial load."""

    l = length
    return (axial_load / (30.0 * l)) * np.asarray(
        [
            [36.0, 3.0 * l, -36.0, 3.0 * l],
            [3.0 * l, 4.0 * l**2, -3.0 * l, -l**2],
            [-36.0, -3.0 * l, 36.0, -3.0 * l],
            [3.0 * l, -l**2, -3.0 * l, 4.0 * l**2],
        ],
        dtype=float,
    )


def _segment_composite_factors(
    config: ExtendedMemberConfig,
    row_sticking: list[bool],
) -> list[float]:
    row_positions = bolt_row_positions(config)
    z_nodes = np.linspace(0.0, config.length, config.n_segments + 1)
    global_factor = float(np.mean(row_sticking)) if row_sticking else 0.0
    factors: list[float] = []
    for seg_idx in range(config.n_segments):
        z0 = z_nodes[seg_idx]
        z1 = z_nodes[seg_idx + 1]
        local = [
            float(row_sticking[row_idx])
            for row_idx, z_row in enumerate(row_positions)
            if z0 < z_row <= z1
        ]
        factors.append(float(np.mean(local)) if local else global_factor)
    return factors


def assemble_beam_matrix(
    config: ExtendedMemberConfig,
    section: SectionProperties,
    row_sticking: list[bool],
) -> tuple[np.ndarray, list[float]]:
    """Assemble the lateral EB beam stiffness for the current interface state."""

    n_nodes = config.n_segments + 1
    matrix = np.zeros((2 * n_nodes, 2 * n_nodes), dtype=float)
    segment_length = config.length / config.n_segments
    composite_factors = _segment_composite_factors(config, row_sticking)
    n_critical = math.pi**2 * section.ei_mono / config.length**2
    axial_load = config.axial_ratio * n_critical if config.p_delta_active else 0.0

    for seg_idx, factor in enumerate(composite_factors):
        ei_eff = section.ei_sep + (section.ei_mono - section.ei_sep) * factor
        local = _beam_stiffness(ei_eff, segment_length)
        if config.p_delta_active:
            local = local - _geometric_stiffness(axial_load, segment_length)
        dofs = [
            2 * seg_idx,
            2 * seg_idx + 1,
            2 * (seg_idx + 1),
            2 * (seg_idx + 1) + 1,
        ]
        for a, dof_a in enumerate(dofs):
            for b, dof_b in enumerate(dofs):
                matrix[dof_a, dof_b] += local[a, b]
    return matrix, composite_factors


def solve_prescribed_top_displacement(
    matrix: np.ndarray,
    config: ExtendedMemberConfig,
    applied_displacement: float,
) -> tuple[np.ndarray, float]:
    """Solve the cantilever with fixed base and prescribed top displacement."""

    n_nodes = config.n_segments + 1
    top_u = 2 * (n_nodes - 1)
    fixed = {0, 1, top_u}
    all_dofs = np.arange(matrix.shape[0])
    free = np.asarray([dof for dof in all_dofs if dof not in fixed], dtype=int)
    prescribed = np.asarray(sorted(fixed), dtype=int)
    values = np.zeros(matrix.shape[0], dtype=float)
    values[top_u] = applied_displacement

    if free.size:
        k_ff = matrix[np.ix_(free, free)]
        rhs = -matrix[np.ix_(free, prescribed)] @ values[prescribed]
        values[free] = np.linalg.solve(k_ff, rhs)

    reactions = matrix @ values
    return values, float(reactions[top_u])


def cantilever_tip_stiffness(
    config: ExtendedMemberConfig,
    composite_factor: float,
) -> float:
    """Return the FE tip stiffness for a uniform composite factor."""

    section = h_section_properties(config)
    row_sticking = [bool(composite_factor >= 0.5)] * config.n_bolt_rows
    if 0.0 < composite_factor < 1.0:
        # Use a direct uniform analytical stiffness for fractional factors.
        ei = section.ei_sep + (section.ei_mono - section.ei_sep) * composite_factor
        return 3.0 * ei / config.length**3
    matrix, _ = assemble_beam_matrix(config, section, row_sticking)
    _, reaction = solve_prescribed_top_displacement(matrix, config, 1.0)
    return abs(reaction)


def _interpolate_u(displacements: np.ndarray, config: ExtendedMemberConfig, z: float) -> float:
    z_nodes = np.linspace(0.0, config.length, config.n_segments + 1)
    u_nodes = displacements[0::2]
    return float(np.interp(z, z_nodes, u_nodes))


def _initial_sticking(config: ExtendedMemberConfig) -> list[bool]:
    if config.mu <= 0.0 or config.q_b0 <= 0.0:
        return [False] * config.n_bolt_rows
    return [True] * config.n_bolt_rows


def _make_connectors(config: ExtendedMemberConfig) -> list[PressureIndexedStickSlip]:
    return [
        PressureIndexedStickSlip(
            k_stick=config.k_stick,
            mu=config.mu,
            pressure_index=config.q_b0,
        )
        for _ in range(config.n_bolt_rows)
    ]


def _make_relaxations(
    config: ExtendedMemberConfig,
    calibration: RelaxationCalibration,
) -> list[BoltPreloadRelaxation]:
    eta_dis = calibration.eta_dis if config.eta_dis is None else config.eta_dis
    q_residual = (
        calibration.q_b_residual
        if config.q_b_residual is None
        else config.q_b_residual
    )
    q_residual = min(max(q_residual, 0.0), config.q_b0)
    return [
        BoltPreloadRelaxation(
            q_b0=config.q_b0,
            q_b_residual=q_residual,
            eta_dis=eta_dis,
        )
        for _ in range(config.n_bolt_rows)
    ]


def _row_slips_from_displacement(
    displacements: np.ndarray,
    config: ExtendedMemberConfig,
) -> list[float]:
    shapes = row_shape_factors(config.n_bolt_rows, config.row_shape_profile)
    top_displacement = float(displacements[-2])
    return [
        config.slip_scale
        * float(shapes[row_idx])
        * max(math.sin(math.pi * z / config.length), 0.0)
        * top_displacement
        for row_idx, z in enumerate(bolt_row_positions(config))
    ]


def _trial_sticking(
    connectors: list[PressureIndexedStickSlip],
    slips: Iterable[float],
) -> list[bool]:
    states: list[bool] = []
    for connector, slip in zip(connectors, slips):
        trial = copy.deepcopy(connector)
        _, sticking = trial.update(float(slip))
        states.append(bool(sticking))
    return states


def _run_step(
    config: ExtendedMemberConfig,
    section: SectionProperties,
    connectors: list[PressureIndexedStickSlip],
    relaxations: list[BoltPreloadRelaxation],
    previous_slips: list[float],
    previous_sticking: list[bool],
    applied_displacement: float,
) -> StepState:
    guess = list(previous_sticking)
    residual_norm = float("inf")
    displacements = np.zeros(2 * (config.n_segments + 1), dtype=float)
    reaction = float("nan")
    row_slips = [float("nan")] * config.n_bolt_rows
    converged = False

    for iteration in range(1, config.max_newton_iterations + 1):
        matrix, _ = assemble_beam_matrix(config, section, guess)
        displacements, reaction = solve_prescribed_top_displacement(
            matrix,
            config,
            applied_displacement,
        )
        row_slips = _row_slips_from_displacement(displacements, config)
        trial = _trial_sticking(connectors, row_slips)
        # Active-set Newton for perfect-plastic connectors: once a row enters
        # sliding within the current load step, keep the lower-composite tangent
        # for the rest of the step. This prevents a two-state tangent oscillation
        # around the yield point while still using the imported connector law for
        # the final state update.
        updated_guess = [bool(a and b) for a, b in zip(trial, guess)]
        residual_norm = float(sum(int(a != b) for a, b in zip(updated_guess, guess)))
        if residual_norm <= config.newton_tol:
            converged = True
            break
        guess = updated_guess

    if not converged:
        return StepState(
            displacements=displacements,
            reaction=float("nan"),
            row_slips=[float("nan")] * config.n_bolt_rows,
            row_forces=[float("nan")] * config.n_bolt_rows,
            row_dissipation_increments=[float("nan")] * config.n_bolt_rows,
            row_q_b=[float("nan")] * config.n_bolt_rows,
            row_sticking=[False] * config.n_bolt_rows,
            composite_factor=float("nan"),
            newton_iterations=config.max_newton_iterations,
            converged=False,
            residual_norm=residual_norm,
        )

    row_forces: list[float] = []
    row_dissipation: list[float] = []
    row_q_b: list[float] = []
    row_sticking: list[bool] = []
    for row_idx, (connector, relaxation, slip) in enumerate(
        zip(connectors, relaxations, row_slips)
    ):
        force, sticking = connector.update(float(slip))
        slip_increment = float(slip - previous_slips[row_idx])
        dissipation_increment = connector.increment_dissipation(slip_increment)
        q_b = relaxation.update(dissipation_increment)
        connector.set_pressure(q_b)

        row_forces.append(float(force))
        row_dissipation.append(float(dissipation_increment))
        row_q_b.append(float(q_b))
        row_sticking.append(bool(sticking))

    return StepState(
        displacements=displacements,
        reaction=reaction,
        row_slips=[float(x) for x in row_slips],
        row_forces=row_forces,
        row_dissipation_increments=row_dissipation,
        row_q_b=row_q_b,
        row_sticking=row_sticking,
        composite_factor=float(np.mean(row_sticking)),
        newton_iterations=iteration,
        converged=True,
        residual_norm=residual_norm,
    )


def run_extended_member_case(
    config: ExtendedMemberConfig | None = None,
    *,
    fit_table: Path | None = None,
) -> dict[str, object]:
    """Run one W3c extended-member cyclic case."""

    config = config or ExtendedMemberConfig()
    fit_table = default_fit_table() if fit_table is None else fit_table
    calibration = load_ds1_calibration(fit_table)
    section = h_section_properties(config)
    connectors = _make_connectors(config)
    relaxations = _make_relaxations(config, calibration)
    protocol = cyclic_displacement_history(
        max_drift=config.max_drift,
        points_per_branch=config.points_per_branch,
    )

    previous_slips = [0.0] * config.n_bolt_rows
    previous_sticking = _initial_sticking(config)
    records: list[dict[str, float | int | bool]] = []
    global_displacements: list[float] = []
    global_reactions: list[float] = []
    composite_history: list[float] = []
    total_iterations = 0
    failures = 0
    residual_norms: list[float] = []

    for step_idx, drift in enumerate(protocol):
        applied = float(drift * config.length)
        state = _run_step(
            config,
            section,
            connectors,
            relaxations,
            previous_slips,
            previous_sticking,
            applied,
        )
        total_iterations += state.newton_iterations
        residual_norms.append(state.residual_norm)

        if not state.converged:
            failures += 1
            previous_sticking = [False] * config.n_bolt_rows
        else:
            previous_slips = list(state.row_slips)
            previous_sticking = list(state.row_sticking)

        global_displacements.append(applied)
        global_reactions.append(state.reaction)
        composite_history.append(state.composite_factor)
        for row_idx in range(config.n_bolt_rows):
            records.append(
                {
                    "step": step_idx,
                    "time_or_drift": float(drift),
                    "applied_displacement": applied,
                    "base_reaction": state.reaction,
                    "row_idx": row_idx,
                    "row_slip": state.row_slips[row_idx],
                    "row_connector_force": state.row_forces[row_idx],
                    "row_dissipation_increment": state.row_dissipation_increments[row_idx],
                    "row_q_b": state.row_q_b[row_idx],
                    "row_sticking_flag": state.row_sticking[row_idx],
                }
            )

    displacement_arr = np.asarray(global_displacements, dtype=float)
    reaction_arr = np.asarray(global_reactions, dtype=float)
    finite = np.isfinite(displacement_arr) & np.isfinite(reaction_arr)
    if np.count_nonzero(finite) >= 2:
        total_loop_energy = float(
            np.sum(
                np.abs(
                    np.diff(displacement_arr[finite])
                    * (reaction_arr[finite][1:] + reaction_arr[finite][:-1])
                    / 2.0
                )
            )
        )
    else:
        total_loop_energy = float("nan")

    per_row_cumulative_dissipation = [
        float(relaxation.cumulative_dissipation) for relaxation in relaxations
    ]
    per_row_final_q_b = [float(relaxation.q_b) for relaxation in relaxations]
    q_residual = relaxations[0].q_b_residual if relaxations else 0.0
    rows_at_floor = [
        idx for idx, q_b in enumerate(per_row_final_q_b) if q_b <= q_residual + 1e-9
    ]

    summary = {
        "peak_base_reaction": float(np.nanmax(np.abs(reaction_arr))),
        "total_loop_energy": total_loop_energy,
        "per_row_cumulative_dissipation": per_row_cumulative_dissipation,
        "per_row_final_q_b": per_row_final_q_b,
        "rows_at_residual_floor": rows_at_floor,
        "n_segments": config.n_segments,
        "n_bolt_rows": config.n_bolt_rows,
        "axial_ratio": config.axial_ratio,
        "p_delta_active": config.p_delta_active,
        "composite_factor_final": float(composite_history[-1]),
        "n_newton_iterations_total": total_iterations,
        "n_newton_failures": failures,
    }

    return {
        "config": config,
        "section": section,
        "history": records,
        "summary": summary,
        "drift": protocol,
        "applied_displacement": displacement_arr,
        "base_reaction": reaction_arr,
        "composite_factor": np.asarray(composite_history, dtype=float),
        "residual_norms": residual_norms,
    }


def write_history_csv(history: list[dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HISTORY_COLUMNS)
        writer.writeheader()
        for row in history:
            writer.writerow(row)


def write_summary_json(summary: dict[str, object], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def write_curves_png(result: dict[str, object], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    history = result["history"]
    config: ExtendedMemberConfig = result["config"]  # type: ignore[assignment]
    drift = result["drift"]
    reaction = result["base_reaction"]
    composite = result["composite_factor"]

    row1 = [row for row in history if row["row_idx"] == 0]
    steps = sorted({int(row["step"]) for row in history})
    q_by_row: list[list[float]] = []
    for row_idx in range(config.n_bolt_rows):
        q_by_row.append(
            [
                float(row["row_q_b"])
                for row in history
                if int(row["row_idx"]) == row_idx
            ]
        )

    fig, axes = plt.subplots(2, 2, figsize=(10.0, 7.2), dpi=160)
    axes[0, 0].plot(drift, reaction, color="#1f4e79", lw=1.2)
    axes[0, 0].set_xlabel("Drift")
    axes[0, 0].set_ylabel("Lateral force")
    axes[0, 0].set_title("Global force-drift")

    axes[0, 1].plot(
        [float(row["row_slip"]) for row in row1],
        [float(row["row_connector_force"]) for row in row1],
        color="#b0442e",
        lw=1.2,
    )
    axes[0, 1].set_xlabel("Row-1 slip")
    axes[0, 1].set_ylabel("Connector force")
    axes[0, 1].set_title("Row-1 force-slip")

    for row_idx, q_values in enumerate(q_by_row):
        axes[1, 0].plot(steps, q_values, lw=1.1, label=f"row {row_idx}")
    axes[1, 0].set_xlabel("Step")
    axes[1, 0].set_ylabel("q_b")
    axes[1, 0].set_title("Preload relaxation")
    axes[1, 0].legend(frameon=False, fontsize=8)

    axes[1, 1].plot(steps, composite, color="#2f6f4e", lw=1.2)
    axes[1, 1].set_xlabel("Step")
    axes[1, 1].set_ylabel("Composite factor")
    axes[1, 1].set_ylim(-0.05, 1.05)
    axes[1, 1].set_title("Sticking-row fraction")

    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)


def run_and_write_toy_case(
    *,
    output_dir: Path,
    fit_table: Path | None = None,
    config: ExtendedMemberConfig | None = None,
) -> dict[str, object]:
    result = run_extended_member_case(config=config, fit_table=fit_table)
    write_history_csv(
        result["history"],
        output_dir / "extended_toy_case_history.csv",
    )
    write_summary_json(
        result["summary"],
        output_dir / "extended_toy_case_summary.json",
    )
    write_curves_png(
        result,
        output_dir / "extended_toy_case_curves.png",
    )
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the W3c extended pure-Python toy case.")
    parser.add_argument(
        "--fit-table",
        type=Path,
        default=default_fit_table(),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_fit_table().parent,
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_and_write_toy_case(output_dir=args.output_dir, fit_table=args.fit_table)
    summary = result["summary"]
    print(f"peak_base_reaction={summary['peak_base_reaction']:.8g}")
    print(f"total_loop_energy={summary['total_loop_energy']:.8g}")
    print(f"per_row_final_q_b={summary['per_row_final_q_b']}")
    print(f"composite_factor_final={summary['composite_factor_final']:.8g}")
    print(f"n_newton_failures={summary['n_newton_failures']}")
    return 0 if summary["n_newton_failures"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
