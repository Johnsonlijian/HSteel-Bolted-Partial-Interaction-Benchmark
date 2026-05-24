"""Smoke tests for the W4 fixed-I_eff sweep design."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

MODULE_PATH = PROJECT_ROOT / "code" / "run_w4_fixed_ieff_sweep.py"
spec = importlib.util.spec_from_file_location("run_w4_fixed_ieff_sweep", MODULE_PATH)
assert spec is not None and spec.loader is not None
w4 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = w4
spec.loader.exec_module(w4)


def test_case_grid_has_30_fixed_section_cases() -> None:
    cases = w4.build_case_grid()
    assert len(cases) == 30
    assert len({case.case_id for case in cases}) == 30
    configs = [w4.config_from_case(case, points_per_branch=4) for case in cases]
    assert len({(cfg.h, cfg.b, cfg.t1, cfg.t2) for cfg in configs}) == 1


def test_fast_sweep_converges_and_spans_labels() -> None:
    rows, history = w4.run_sweep(points_per_branch=4)
    assert len(rows) == 30
    assert history
    assert sum(bool(row["converged"]) for row in rows) >= 25
    assert len({row["weak_state_label"] for row in rows}) >= 3
    assert all(float(row["total_loop_energy"]) >= float(row["total_row_dissipation"]) for row in rows)


if __name__ == "__main__":
    test_case_grid_has_30_fixed_section_cases()
    test_fast_sweep_converges_and_spans_labels()
    print("test_w4_fixed_ieff_sweep.py: PASS")
