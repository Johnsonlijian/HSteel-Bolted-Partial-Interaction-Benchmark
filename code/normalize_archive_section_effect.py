"""Normalize archive RF2 ratios by a transparent section-effect proxy.

W3 Thread B reads the R05 anchor table, parses H-section dimensions from
``study_key``, and estimates how much of the separated/overall RF2 ratio can
be attributed to the archive section representation. The separated model used
here follows the W3 acceptance gate wording: two smaller, non-composite
half-height H limbs, compared against one monolithic H-section.

Post-W3b warning: local source-script audit found that the physical archive
meaning is full-height separated H instances, not half-height limbs. Keep this
file as the W3 gate artifact; use ``normalize_archive_section_effect_w3b.py``
for manuscript-facing interpretation.
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path


REQUIRED_OUTPUT_COLUMNS = [
    "study_key",
    "archive_peak_abs_rf2_ratio",
    "i_eff_mono_mm4",
    "i_eff_sep_mm4",
    "i_eff_ratio_mono_over_sep",
    "normalized_rf2_ratio",
    "candidate_role",
    "section_effect_dominates_flag",
    "normalization_note",
    "i_eff_sep_model",
]

SEP_MODEL = (
    "two_half_height_H_limbs_non_composite; "
    "I_sep=2*I_centroidal(H/2,B,T1,T2); no global parallel-axis composite action"
)


@dataclass(frozen=True)
class SectionGeometry:
    """H-section dimensions parsed from an archive study key, in millimetres."""

    h: float
    b: float
    t1: float
    t2: float


def parse_study_key(study_key: str) -> SectionGeometry:
    """Parse ``H``, ``B``, ``T1`` and ``T2`` from a pipe-delimited study key."""

    parts: dict[str, str] = {}
    for token in study_key.split("|"):
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        parts[key.strip()] = value.strip()

    missing = [key for key in ("H", "B", "T1", "T2") if key not in parts]
    if missing:
        raise ValueError(f"study_key missing section fields {missing}: {study_key}")

    geom = SectionGeometry(
        h=float(parts["H"]),
        b=float(parts["B"]),
        t1=float(parts["T1"]),
        t2=float(parts["T2"]),
    )
    validate_geometry(geom)
    return geom


def validate_geometry(geom: SectionGeometry) -> None:
    """Reject impossible H-section dimensions before inertia calculations."""

    if min(geom.h, geom.b, geom.t1, geom.t2) <= 0:
        raise ValueError(f"section dimensions must be positive: {geom}")
    if geom.t1 >= geom.b:
        raise ValueError(f"T1 must be smaller than B for the void formula: {geom}")
    if 2.0 * geom.t2 >= geom.h:
        raise ValueError(f"2*T2 must be smaller than H: {geom}")
    if 2.0 * geom.t2 >= geom.h / 2.0:
        raise ValueError(
            "half-height separated limb would have no web clear height: "
            f"{geom}"
        )


def h_section_strong_axis_inertia(h: float, b: float, t1: float, t2: float) -> float:
    """Strong-axis inertia for the idealized H-section used in the W3 brief."""

    return (b * h**3 - (b - t1) * (h - 2.0 * t2) ** 3) / 12.0


def section_effect_values(geom: SectionGeometry) -> tuple[float, float, float]:
    """Return monolithic I, separated-limb I, and ``I_mono / I_sep``.

    The separated representation is intentionally non-composite: the two
    half-height limbs are treated as independent sections, so their centroidal
    inertias add without a global parallel-axis term. That choice matches the
    acceptance gate's requirement that the monolithic section has higher
    effective bending inertia than the separated representation.
    """

    i_mono = h_section_strong_axis_inertia(geom.h, geom.b, geom.t1, geom.t2)
    half_h = geom.h / 2.0
    i_half = h_section_strong_axis_inertia(half_h, geom.b, geom.t1, geom.t2)
    i_sep = 2.0 * i_half
    if not (math.isfinite(i_mono) and math.isfinite(i_sep)) or i_mono <= 0 or i_sep <= 0:
        raise ValueError(f"non-positive or non-finite inertia for {geom}")
    return i_mono, i_sep, i_mono / i_sep


def normalize_rf2_ratio(raw_ratio: float, inertia_ratio: float) -> float:
    """Move the raw RF2 ratio toward unity by the section-effect contrast.

    ``inertia_ratio`` is greater than one. Instead of forcing a multiplicative
    correction that can overshoot unity, the residual contrast from unity is
    reduced by the stiffness contrast:

    ``normalized = 1 + (raw - 1) / inertia_ratio``.
    """

    if inertia_ratio <= 1.0 or not math.isfinite(inertia_ratio):
        raise ValueError(f"inertia_ratio must be finite and > 1: {inertia_ratio}")
    return 1.0 + (raw_ratio - 1.0) / inertia_ratio


def section_effect_dominates(raw_ratio: float, normalized_ratio: float) -> bool:
    """Apply the W3 brief dominance formula."""

    return abs(normalized_ratio - 1.0) < 0.1 * abs(raw_ratio - 1.0)


def normalize_anchor_row(row: dict[str, str]) -> dict[str, str]:
    """Normalize one R05 anchor row and return CSV-ready values."""

    study_key = row["study_key"]
    raw_ratio = float(row["archive_peak_abs_rf2_ratio"])
    geom = parse_study_key(study_key)
    i_mono, i_sep, ratio = section_effect_values(geom)
    normalized = normalize_rf2_ratio(raw_ratio, ratio)
    flag = section_effect_dominates(raw_ratio, normalized)
    note = (
        "raw RF2 contrast moved toward unity by I_mono/I_sep; "
        "separated model follows W3 gate #12 smaller-H non-composite assumption"
    )

    return {
        "study_key": study_key,
        "archive_peak_abs_rf2_ratio": f"{raw_ratio:.12g}",
        "i_eff_mono_mm4": f"{i_mono:.12g}",
        "i_eff_sep_mm4": f"{i_sep:.12g}",
        "i_eff_ratio_mono_over_sep": f"{ratio:.12g}",
        "normalized_rf2_ratio": f"{normalized:.12g}",
        "candidate_role": row.get("candidate_role", ""),
        "section_effect_dominates_flag": str(flag).lower(),
        "normalization_note": note,
        "i_eff_sep_model": SEP_MODEL,
    }


def normalize_file(anchor_links: Path, out: Path) -> tuple[int, int]:
    """Normalize all R05 anchors and write the W3 output CSV."""

    with anchor_links.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"empty input CSV: {anchor_links}")
        required = {"study_key", "archive_peak_abs_rf2_ratio", "candidate_role"}
        missing = sorted(required.difference(reader.fieldnames))
        if missing:
            raise ValueError(f"input missing required columns {missing}")
        normalized_rows = [normalize_anchor_row(row) for row in reader]

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REQUIRED_OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(normalized_rows)

    dominates = sum(
        row["section_effect_dominates_flag"] == "true" for row in normalized_rows
    )
    return len(normalized_rows), dominates


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Normalize archive RF2 ratios by H-section inertia contrast."
    )
    parser.add_argument("--anchor-links", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    n_rows, dominates = normalize_file(args.anchor_links, args.out)
    print(
        f"W3 Thread B wrote {n_rows} rows to {args.out}; "
        f"section_effect_dominates={dominates}/{n_rows}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
