"""OpenSeesPy scaffold for the W3 relaxation-coupled toy benchmark.

The local environment used for W3a does not currently expose an importable
OpenSeesPy backend or an OpenSees CLI. This module is therefore written as an
auditable scaffold: it imports the project interface laws, defines the coupling
wrapper that a zero-length OpenSees material adapter must call between
increments, and exits without generating fake benchmark CSV/JSON/PNG outputs
when OpenSees is absent.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from solver.interface_law import (
    BoltPreloadRelaxation,
    PressureIndexedStickSlip,
    couple_relaxation_to_connector,
)
from solver.reduced_member_model import cyclic_displacement_history


@dataclass(frozen=True)
class RelaxationCalibration:
    """W2 ds1 calibration constants used for the W3 toy case."""

    eta_dis: float
    q_b_residual: float


def load_ds1_calibration(fit_table: Path) -> RelaxationCalibration:
    """Load the ds1 steel-bolt calibration row from the W2 fit table."""

    with fit_table.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["dataset_id"] == "ds1_eraliev2021_m12_120c":
                return RelaxationCalibration(
                    eta_dis=float(row["eta_dis"]),
                    q_b_residual=float(row["q_b_residual"]),
                )
    raise ValueError(f"ds1 calibration row not found in {fit_table}")


def has_openseespy() -> bool:
    """Return true only when OpenSeesPy can actually be imported locally."""

    try:
        import openseespy.opensees  # noqa: F401
    except Exception:
        return False
    return True


def openseespy_import_error() -> str:
    """Return the OpenSeesPy import error, or an empty string when import works."""

    try:
        import openseespy.opensees  # noqa: F401
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"
    return ""


def has_opensees_cli() -> bool:
    """Return true when an OpenSees executable is already on PATH."""

    return shutil.which("OpenSees") is not None


def w3_cyclic_protocol() -> list[float]:
    """Use the exact reduced-member W3 protocol: 3 amplitudes, 30 points/branch."""

    return cyclic_displacement_history(max_drift=0.04, points_per_branch=30).tolist()


def make_relaxation_coupled_connector(
    calibration: RelaxationCalibration,
    *,
    k_stick: float = 120.0,
    mu: float = 0.35,
    q_b0: float = 1.0,
) -> tuple[PressureIndexedStickSlip, BoltPreloadRelaxation]:
    """Build the project-law connector pair for one OpenSees material wrapper."""

    connector = PressureIndexedStickSlip(
        k_stick=k_stick,
        mu=mu,
        pressure_index=q_b0,
    )
    relaxation = BoltPreloadRelaxation(
        q_b0=q_b0,
        q_b_residual=calibration.q_b_residual,
        eta_dis=calibration.eta_dis,
    )
    return connector, relaxation


def advance_material_wrapper(
    connector: PressureIndexedStickSlip,
    relaxation: BoltPreloadRelaxation,
    slip: float,
    previous_slip: float,
) -> tuple[float, float, bool, float]:
    """Advance the imported W2 laws for one OpenSees displacement increment.

    This is the required W3 wrapper point: OpenSees supplies ``slip``;
    ``PressureIndexedStickSlip.update()`` computes the connector force; the
    imported ``BoltPreloadRelaxation.update()`` is reached through
    ``couple_relaxation_to_connector`` so the preload index is updated between
    increments without reimplementing the decay rule in this file.
    """

    connector.update(slip)
    slip_increment = slip - previous_slip
    q_b, force, sticking = couple_relaxation_to_connector(
        connector,
        relaxation,
        slip_increment,
    )
    dissipation = relaxation.cumulative_dissipation
    return q_b, force, sticking, dissipation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="W3 OpenSeesPy toy-case scaffold.")
    parser.add_argument(
        "--fit-table",
        type=Path,
        default=Path("rounds/R06_path2_opensees_benchmark/outputs/relaxation_fit_table.csv"),
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Verify imports, protocol, calibration and local OpenSees availability.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    calibration = load_ds1_calibration(args.fit_table)
    connector, relaxation = make_relaxation_coupled_connector(calibration)
    protocol = w3_cyclic_protocol()
    q_b, force, sticking, dissipation = advance_material_wrapper(
        connector,
        relaxation,
        slip=protocol[1],
        previous_slip=protocol[0],
    )

    print(f"ds1_eta_dis={calibration.eta_dis:.8g}")
    print(f"ds1_q_b_residual={calibration.q_b_residual:.8g}")
    print(f"cyclic_protocol_points={len(protocol)}")
    print(f"single_wrapper_step_q_b={q_b:.8g}")
    print(f"single_wrapper_step_force={force:.8g}")
    print(f"single_wrapper_step_sticking={sticking}")
    print(f"single_wrapper_cumulative_dissipation={dissipation:.8g}")
    print(f"openseespy_available={has_openseespy()}")
    error = openseespy_import_error()
    if error:
        print(f"openseespy_import_error={error}")
    print(f"opensees_cli_available={has_opensees_cli()}")

    if args.check_only:
        return 0

    print(
        "OpenSees backend is unavailable in this offline W3 environment; "
        "no toy-case CSV/JSON/PNG outputs were generated."
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
