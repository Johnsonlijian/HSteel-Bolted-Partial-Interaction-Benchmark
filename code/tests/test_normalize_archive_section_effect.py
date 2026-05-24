"""Smoke tests for W3 archive section-effect normalization."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = PROJECT_ROOT / "code" / "normalize_archive_section_effect.py"

spec = importlib.util.spec_from_file_location("normalize_archive_section_effect", MODULE_PATH)
assert spec is not None and spec.loader is not None
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_parse_and_normalize_round_trip() -> None:
    row = {
        "candidate_role": "synthetic_anchor",
        "study_key": (
            "H=200|B=100|T1=5.5|T2=8|L=3000|n_or_E=1|F=4|"
            "BoltD=20|BoltB=0|meshsz=40"
        ),
        "archive_peak_abs_rf2_ratio": "1.70851",
    }

    out = mod.normalize_anchor_row(row)

    assert out["study_key"] == row["study_key"]
    assert out["candidate_role"] == "synthetic_anchor"
    assert float(out["i_eff_mono_mm4"]) > 0.0
    assert float(out["i_eff_sep_mm4"]) > 0.0
    assert float(out["i_eff_ratio_mono_over_sep"]) > 1.0
    raw = float(out["archive_peak_abs_rf2_ratio"])
    normalized = float(out["normalized_rf2_ratio"])
    assert 1.0 < normalized < raw
    expected_flag = abs(normalized - 1.0) < 0.1 * abs(raw - 1.0)
    assert out["section_effect_dominates_flag"] == str(expected_flag).lower()
    assert "two_half_height_H_limbs_non_composite" in out["i_eff_sep_model"]


if __name__ == "__main__":
    test_parse_and_normalize_round_trip()
    print("test_normalize_archive_section_effect.py: PASS")
