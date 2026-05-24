"""Tests for source-audited W3b section-effect normalization."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = PROJECT_ROOT / "code" / "normalize_archive_section_effect_w3b.py"

spec = importlib.util.spec_from_file_location("normalize_archive_section_effect_w3b", MODULE_PATH)
assert spec is not None and spec.loader is not None
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_e1_has_no_section_stack_correction() -> None:
    row = {
        "candidate_role": "positive_interface_sensitivity_anchor",
        "study_key": "H=100|B=100|T1=6|T2=8|L=3000|n_or_E=1|F=4",
        "archive_peak_abs_rf2_ratio": "1.64136",
    }
    out = mod.normalize_row(row)
    assert out["n_or_E"] == "1"
    assert float(out["i_eff_ratio_mono_over_sep"]) == 1.0
    assert float(out["normalized_rf2_ratio"]) == float(row["archive_peak_abs_rf2_ratio"])
    assert out["section_effect_dominates_flag"] == "false"


def test_e5_full_stack_correction_moves_toward_unity() -> None:
    row = {
        "candidate_role": "negative_interface_sensitivity_anchor",
        "study_key": "H=100|B=100|T1=6|T2=8|L=3000|n_or_E=5|F=4",
        "archive_peak_abs_rf2_ratio": "0.474031",
    }
    out = mod.normalize_row(row)
    raw = float(out["archive_peak_abs_rf2_ratio"])
    normalized = float(out["normalized_rf2_ratio"])
    assert float(out["i_eff_ratio_mono_over_sep"]) > 10.0
    assert raw < normalized < 1.0
    assert out["section_effect_dominates_flag"] == "true"
    assert "full_height_H_instances_non_composite" in out["i_eff_sep_model"]


if __name__ == "__main__":
    test_e1_has_no_section_stack_correction()
    test_e5_full_stack_correction_moves_toward_unity()
    print("test_normalize_archive_section_effect_w3b.py: PASS")
