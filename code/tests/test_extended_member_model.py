"""Sanity tests for the W3c extended pure-Python member model."""

from __future__ import annotations

import sys
from pathlib import Path
import os


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from solver.extended_member_model import (  # noqa: E402
    ExtendedMemberConfig,
    h_section_properties,
    run_extended_member_case,
)


def _fit_table() -> Path:
    env_value = os.environ.get("HSTEEL_OUTPUT_DIR")
    if env_value:
        path = Path(env_value)
        output_dir = path if path.is_absolute() else PROJECT_ROOT / path
        return output_dir / "relaxation_fit_table.csv"
    public_outputs = PROJECT_ROOT / "outputs"
    if public_outputs.exists() and not (PROJECT_ROOT / "rounds").exists():
        return public_outputs / "relaxation_fit_table.csv"
    return (
        PROJECT_ROOT
        / "rounds"
        / "R06_path2_opensees_benchmark"
        / "outputs"
        / "relaxation_fit_table.csv"
    )


FIT_TABLE = _fit_table()


def _analytical_peak_force(config: ExtendedMemberConfig, ei: float) -> float:
    peak_displacement = config.max_drift * config.length
    stiffness = 3.0 * ei / config.length**3
    return stiffness * peak_displacement


def test_zero_friction_limit_matches_two_limb_parallel_stiffness() -> None:
    config = ExtendedMemberConfig(
        mu=0.0,
        q_b0=1.0,
        eta_dis=0.0,
        q_b_residual=0.0,
        p_delta_active=False,
        points_per_branch=6,
    )
    result = run_extended_member_case(config, fit_table=FIT_TABLE)
    section = h_section_properties(config)
    expected = _analytical_peak_force(config, section.ei_sep)
    actual = float(result["summary"]["peak_base_reaction"])
    rel_err = abs(actual - expected) / expected
    assert rel_err <= 0.05, f"zero-friction limit rel_err={rel_err:.4f}"


def test_infinite_friction_limit_matches_monolithic_stiffness() -> None:
    config = ExtendedMemberConfig(
        mu=0.35,
        q_b0=1.0e9,
        eta_dis=0.0,
        q_b_residual=0.0,
        p_delta_active=False,
        points_per_branch=6,
    )
    result = run_extended_member_case(config, fit_table=FIT_TABLE)
    section = h_section_properties(config)
    expected = _analytical_peak_force(config, section.ei_mono)
    actual = float(result["summary"]["peak_base_reaction"])
    rel_err = abs(actual - expected) / expected
    assert rel_err <= 0.10, f"infinite-friction limit rel_err={rel_err:.4f}"


def test_energy_bookkeeping_bounds_row_dissipation() -> None:
    config = ExtendedMemberConfig(points_per_branch=6)
    result = run_extended_member_case(config, fit_table=FIT_TABLE)
    summary = result["summary"]
    row_dissipation = sum(summary["per_row_cumulative_dissipation"])
    loop_energy = float(summary["total_loop_energy"])
    assert row_dissipation > 0.0
    assert loop_energy > 0.0
    assert loop_energy >= row_dissipation


if __name__ == "__main__":
    test_zero_friction_limit_matches_two_limb_parallel_stiffness()
    test_infinite_friction_limit_matches_monolithic_stiffness()
    test_energy_bookkeeping_bounds_row_dissipation()
    print("test_extended_member_model.py: PASS")
