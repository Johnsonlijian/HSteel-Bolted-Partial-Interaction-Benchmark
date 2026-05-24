"""Smoke tests for the W5 full fixed-I_eff benchmark."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

MODULE_PATH = PROJECT_ROOT / "code" / "run_w5_full_benchmark.py"
spec = importlib.util.spec_from_file_location("run_w5_full_benchmark", MODULE_PATH)
assert spec is not None and spec.loader is not None
w5 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = w5
spec.loader.exec_module(w5)


def test_w5_grid_has_90_cases_in_three_fixed_slices() -> None:
    cases = w5.build_case_grid()
    assert len(cases) == 90
    assert len({case.case_id for case in cases}) == 90
    assert len({case.section.name for case in cases}) == 3
    configs = [w5.config_from_case(case, points_per_branch=4) for case in cases]
    for section in w5.section_slices():
        subset = [
            cfg
            for case, cfg in zip(cases, configs)
            if case.section.name == section.name
        ]
        assert len({(cfg.h, cfg.b, cfg.t1, cfg.t2) for cfg in subset}) == 1


def test_w5_fast_benchmark_converges_and_spans_labels() -> None:
    rows, history = w5.run_benchmark(points_per_branch=4)
    assert len(rows) == 90
    assert history
    assert sum(bool(row["converged"]) for row in rows) / len(rows) >= 0.80
    slice_counts = w5._slice_label_counts(rows)
    assert max(len(counts) for counts in slice_counts.values()) >= 3
    assert all(float(row["total_loop_energy"]) >= float(row["total_row_dissipation"]) for row in rows)


if __name__ == "__main__":
    test_w5_grid_has_90_cases_in_three_fixed_slices()
    test_w5_fast_benchmark_converges_and_spans_labels()
    print("test_w5_full_benchmark.py: PASS")
