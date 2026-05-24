"""Run the W4 fixed-I_eff 30-case sweep for the Path-C solver.

This script is deliberately offline and deterministic. It keeps the H-section
geometry fixed (the first fixed-I_eff slice) while varying interface and
stability parameters, then writes the summary table, long time-history table,
and a Figure-4 prototype.
"""

from __future__ import annotations

import csv
import json
import math
import os
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from solver.extended_member_model import (  # noqa: E402
    ExtendedMemberConfig,
    h_section_properties,
    run_extended_member_case,
)
from solver.labels import classify_response  # noqa: E402


def resolve_output_dir() -> Path:
    env_value = os.environ.get("HSTEEL_OUTPUT_DIR")
    if env_value:
        path = Path(env_value)
        return path if path.is_absolute() else PROJECT_ROOT / path
    public_outputs = PROJECT_ROOT / "outputs"
    if public_outputs.exists() and not (PROJECT_ROOT / "rounds").exists():
        return public_outputs
    return PROJECT_ROOT / "rounds" / "R06_path2_opensees_benchmark" / "outputs"


OUTPUT_DIR = resolve_output_dir()
FIT_TABLE = OUTPUT_DIR / "relaxation_fit_table.csv"

SUMMARY_CSV = OUTPUT_DIR / "w4_fixed_ieff_sweep_summary.csv"
HISTORY_CSV = OUTPUT_DIR / "w4_fixed_ieff_sweep_history.csv"
SUMMARY_JSON = OUTPUT_DIR / "w4_fixed_ieff_sweep_summary.json"
FIGURE_PNG = OUTPUT_DIR / "w4_fixed_ieff_figure4_prototype.png"


SUMMARY_COLUMNS = [
    "case_id",
    "ieff_slice",
    "h",
    "b",
    "t1",
    "t2",
    "length",
    "slenderness",
    "mu",
    "q_b0",
    "bolt_rows",
    "axial_ratio",
    "k_stick",
    "peak_base_reaction",
    "total_loop_energy",
    "total_row_dissipation",
    "final_min_q_b",
    "final_mean_q_b",
    "rows_relaxed",
    "composite_factor_final",
    "max_abs_row_slip",
    "slip_index",
    "local_buckling_index",
    "global_instability_index",
    "energy_index",
    "weak_state_label",
    "n_newton_iterations_total",
    "n_newton_failures",
    "converged",
]


HISTORY_COLUMNS = [
    "case_id",
    "weak_state_label",
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
class W4Case:
    case_id: str
    slenderness: float
    mu: float
    q_b0: float
    bolt_rows: int
    axial_ratio: float


def build_case_grid() -> list[W4Case]:
    """Return the 30 deterministic cases for the first fixed-I_eff slice."""

    axial_slender_pairs = [
        (0.10, 35.0),
        (0.25, 55.0),
        (0.40, 75.0),
        (0.55, 95.0),
        (0.70, 115.0),
    ]
    interface_pairs = [
        (0.20, 0.70),
        (0.35, 1.00),
        (0.55, 1.30),
    ]
    cases: list[W4Case] = []
    counter = 1
    for axial_ratio, slenderness in axial_slender_pairs:
        for bolt_rows in (3, 5):
            for mu, q_b0 in interface_pairs:
                cases.append(
                    W4Case(
                        case_id=f"W4-{counter:02d}",
                        slenderness=slenderness,
                        mu=mu,
                        q_b0=q_b0,
                        bolt_rows=bolt_rows,
                        axial_ratio=axial_ratio,
                    )
                )
                counter += 1
    return cases


def config_from_case(case: W4Case, *, points_per_branch: int = 30) -> ExtendedMemberConfig:
    """Build a fixed-section config while varying length as the slenderness proxy."""

    baseline_length = 3000.0
    baseline_slenderness = 55.0
    length = baseline_length * math.sqrt(case.slenderness / baseline_slenderness)
    return ExtendedMemberConfig(
        length=length,
        h=100.0,
        b=100.0,
        t1=6.0,
        t2=8.0,
        mu=case.mu,
        q_b0=case.q_b0,
        n_bolt_rows=case.bolt_rows,
        axial_ratio=case.axial_ratio,
        points_per_branch=points_per_branch,
        p_delta_active=True,
    )


def _local_buckling_index(config: ExtendedMemberConfig, slenderness: float) -> float:
    base = 0.028
    slender_factor = max(0.35, 70.0 / max(slenderness, 1.0))
    axial_factor = max(0.25, 1.0 - 0.65 * config.axial_ratio)
    row_factor = 1.0 + 0.035 * max(0, config.n_bolt_rows - 3)
    delta_lb = base * slender_factor * axial_factor * row_factor
    return max(0.0, config.max_drift / max(delta_lb, 1e-9) - 1.0)


def summarize_case(case: W4Case, result: dict[str, object], config: ExtendedMemberConfig) -> dict[str, object]:
    history = result["history"]
    summary = result["summary"]
    section = h_section_properties(config)

    max_abs_slip = max(abs(float(row["row_slip"])) for row in history)
    yield_slip = config.mu * config.q_b0 / max(config.k_stick, 1e-12)
    slip_index = max_abs_slip / max(yield_slip, 1e-12)
    peak = float(summary["peak_base_reaction"])
    loop_energy = float(summary["total_loop_energy"])
    max_displacement = config.max_drift * config.length
    energy_index = loop_energy / max(abs(peak) * max_displacement, 1e-12)
    local_index = _local_buckling_index(config, case.slenderness)
    global_index = config.axial_ratio * case.slenderness / 52.0
    weak_label = classify_response(
        slip_index=slip_index,
        local_buckling_index=local_index,
        global_instability_index=global_index,
        energy_index=energy_index,
    )

    final_q = [float(q) for q in summary["per_row_final_q_b"]]
    total_dissipation = float(sum(summary["per_row_cumulative_dissipation"]))
    converged = int(summary["n_newton_failures"]) == 0

    return {
        "case_id": case.case_id,
        "ieff_slice": "H100_B100_T1-6_T2-8",
        "h": config.h,
        "b": config.b,
        "t1": config.t1,
        "t2": config.t2,
        "length": config.length,
        "slenderness": case.slenderness,
        "mu": config.mu,
        "q_b0": config.q_b0,
        "bolt_rows": config.n_bolt_rows,
        "axial_ratio": config.axial_ratio,
        "k_stick": config.k_stick,
        "peak_base_reaction": peak,
        "total_loop_energy": loop_energy,
        "total_row_dissipation": total_dissipation,
        "final_min_q_b": min(final_q),
        "final_mean_q_b": float(np.mean(final_q)),
        "rows_relaxed": int(sum(q < config.q_b0 - 1e-9 for q in final_q)),
        "composite_factor_final": float(summary["composite_factor_final"]),
        "max_abs_row_slip": max_abs_slip,
        "slip_index": slip_index,
        "local_buckling_index": local_index,
        "global_instability_index": global_index,
        "energy_index": energy_index,
        "weak_state_label": weak_label,
        "n_newton_iterations_total": int(summary["n_newton_iterations_total"]),
        "n_newton_failures": int(summary["n_newton_failures"]),
        "converged": converged,
        "i_single": section.i_single,
        "i_sep": section.i_sep,
        "i_mono": section.i_mono,
    }


def run_sweep(*, points_per_branch: int = 30) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    case_summaries: list[dict[str, object]] = []
    history_rows: list[dict[str, object]] = []
    for case in build_case_grid():
        config = config_from_case(case, points_per_branch=points_per_branch)
        result = run_extended_member_case(config=config, fit_table=FIT_TABLE)
        row = summarize_case(case, result, config)
        case_summaries.append(row)
        for hist_row in result["history"]:
            history_rows.append(
                {
                    "case_id": case.case_id,
                    "weak_state_label": row["weak_state_label"],
                    **hist_row,
                }
            )
    return case_summaries, history_rows


def write_csv(rows: list[dict[str, object]], path: Path, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def write_summary_json(rows: list[dict[str, object]], path: Path) -> None:
    counts = Counter(str(row["weak_state_label"]) for row in rows)
    payload = {
        "n_cases": len(rows),
        "n_converged": sum(bool(row["converged"]) for row in rows),
        "n_failed": sum(not bool(row["converged"]) for row in rows),
        "n_labels": len(counts),
        "label_counts": dict(sorted(counts.items())),
        "ieff_slice": "H100_B100_T1-6_T2-8",
        "fixed_section_columns": ["h", "b", "t1", "t2"],
        "case_grid": {
            "axial_ratio": sorted({float(row["axial_ratio"]) for row in rows}),
            "slenderness": sorted({float(row["slenderness"]) for row in rows}),
            "mu": sorted({float(row["mu"]) for row in rows}),
            "q_b0": sorted({float(row["q_b0"]) for row in rows}),
            "bolt_rows": sorted({int(row["bolt_rows"]) for row in rows}),
        },
    }
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def write_figure(rows: list[dict[str, object]], history_rows: list[dict[str, object]], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = sorted({str(row["weak_state_label"]) for row in rows})
    palette = {
        "stiff_composite_like": "#3f6f9f",
        "slip_dominated": "#b0442e",
        "mixed_slip_stability": "#7a5195",
        "local_buckling_softening": "#d79a2b",
        "global_instability_sensitive": "#2f6f4e",
    }
    case_x = np.arange(1, len(rows) + 1)
    colors = [palette[str(row["weak_state_label"])] for row in rows]

    fig, axes = plt.subplots(2, 2, figsize=(11.0, 8.0), dpi=160)

    for label in labels:
        selected = [row for row in rows if row["weak_state_label"] == label]
        axes[0, 0].scatter(
            [float(row["global_instability_index"]) for row in selected],
            [float(row["slip_index"]) for row in selected],
            s=[38.0 + 60.0 * (1.0 - float(row["final_min_q_b"]) / float(row["q_b0"])) for row in selected],
            color=palette[label],
            edgecolor="white",
            linewidth=0.5,
            label=label.replace("_", " "),
        )
    axes[0, 0].set_xlabel("Global-instability index")
    axes[0, 0].set_ylabel("Slip index")
    axes[0, 0].set_title("Fixed-I_eff response-state map")
    axes[0, 0].legend(frameon=False, fontsize=7)

    axes[0, 1].bar(case_x, [float(row["peak_base_reaction"]) for row in rows], color=colors)
    axes[0, 1].set_xlabel("Case index")
    axes[0, 1].set_ylabel("Peak base reaction")
    axes[0, 1].set_title("Peak force across 30 cases")

    relaxation_scatter = axes[1, 0].scatter(
        [float(row["mu"]) for row in rows],
        [float(row["final_min_q_b"]) / float(row["q_b0"]) for row in rows],
        c=[float(row["axial_ratio"]) for row in rows],
        cmap="viridis",
        s=[32 + 10 * int(row["bolt_rows"]) for row in rows],
        edgecolor="white",
        linewidth=0.4,
    )
    axes[1, 0].set_xlabel("Friction coefficient mu")
    axes[1, 0].set_ylabel("Final min(q_b) / q_b0")
    axes[1, 0].set_title("Relaxation severity")
    cbar = fig.colorbar(relaxation_scatter, ax=axes[1, 0], fraction=0.046, pad=0.04)
    cbar.set_label("Axial ratio")

    representatives: dict[str, str] = {}
    for label in labels:
        candidates = [row for row in rows if row["weak_state_label"] == label]
        representatives[label] = min(candidates, key=lambda row: float(row["final_min_q_b"]))["case_id"]
    for label, case_id in representatives.items():
        case_summary = next(row for row in rows if row["case_id"] == case_id)
        q_b0 = float(case_summary["q_b0"])
        rows_for_case = [row for row in history_rows if row["case_id"] == case_id]
        steps = sorted({int(row["step"]) for row in rows_for_case})
        min_q_by_step = []
        for step in steps:
            q_values = [
                float(row["row_q_b"])
                for row in rows_for_case
                if int(row["step"]) == step
            ]
            min_q_by_step.append(min(q_values) / q_b0)
        axes[1, 1].plot(
            np.linspace(0.0, 1.0, len(steps)),
            min_q_by_step,
            color=palette[label],
            lw=1.1,
            label=f"{case_id} {label.replace('_', ' ')}",
        )
    axes[1, 1].set_xlabel("Normalized cyclic step")
    axes[1, 1].set_ylabel("Minimum row q_b / q_b0")
    axes[1, 1].set_title("Representative normalized q_b trajectories")
    axes[1, 1].legend(frameon=False, fontsize=6)

    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)


def main() -> int:
    rows, history = run_sweep(points_per_branch=30)
    write_csv(rows, SUMMARY_CSV, SUMMARY_COLUMNS)
    write_csv(history, HISTORY_CSV, HISTORY_COLUMNS)
    write_summary_json(rows, SUMMARY_JSON)
    write_figure(rows, history, FIGURE_PNG)

    counts = Counter(str(row["weak_state_label"]) for row in rows)
    n_converged = sum(bool(row["converged"]) for row in rows)
    print(f"w4_cases={len(rows)}")
    print(f"w4_converged={n_converged}")
    print(f"w4_failed={len(rows) - n_converged}")
    print(f"w4_label_counts={dict(sorted(counts.items()))}")
    print(f"w4_outputs={SUMMARY_CSV};{HISTORY_CSV};{SUMMARY_JSON};{FIGURE_PNG}")
    return 0 if n_converged >= 25 and len(counts) >= 3 else 2


if __name__ == "__main__":
    raise SystemExit(main())
