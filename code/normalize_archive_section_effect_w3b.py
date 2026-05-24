"""W3b source-audited archive section-effect normalization.

W3 initially used the acceptance gate's "two smaller H" wording. A local
source audit found that the separated Abaqus scripts pattern full-height H
instances, while the overall scripts pattern the same H geometry in a single
monolithic part. This script keeps W3 intact and writes a corrected W3b table.
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path


FIELDNAMES = [
    "study_key",
    "n_or_E",
    "archive_peak_abs_rf2_ratio",
    "i_eff_mono_mm4",
    "i_eff_sep_mm4",
    "i_eff_ratio_mono_over_sep",
    "normalized_rf2_ratio",
    "candidate_role",
    "section_effect_dominates_flag",
    "normalization_note",
    "i_eff_sep_model",
    "source_basis",
]


@dataclass(frozen=True)
class Geometry:
    h: float
    b: float
    t1: float
    t2: float
    n_or_e: int


def parse_study_key(study_key: str) -> Geometry:
    parts = {}
    for token in study_key.split("|"):
        if "=" in token:
            key, value = token.split("=", 1)
            parts[key] = value
    missing = [key for key in ("H", "B", "T1", "T2", "n_or_E") if key not in parts]
    if missing:
        raise ValueError(f"study_key missing {missing}: {study_key}")
    geom = Geometry(
        h=float(parts["H"]),
        b=float(parts["B"]),
        t1=float(parts["T1"]),
        t2=float(parts["T2"]),
        n_or_e=int(float(parts["n_or_E"])),
    )
    if min(geom.h, geom.b, geom.t1, geom.t2) <= 0:
        raise ValueError(f"non-positive section field: {geom}")
    if geom.t1 >= geom.b or 2.0 * geom.t2 >= geom.h:
        raise ValueError(f"invalid H-section proportions: {geom}")
    if geom.n_or_e < 1:
        raise ValueError(f"n_or_E must be >= 1: {geom}")
    return geom


def h_inertia(h: float, b: float, t1: float, t2: float) -> float:
    return (b * h**3 - (b - t1) * (h - 2.0 * t2) ** 3) / 12.0


def h_area(h: float, b: float, t1: float, t2: float) -> float:
    return b * h - (b - t1) * (h - 2.0 * t2)


def corrected_section_values(geom: Geometry) -> tuple[float, float, float]:
    """Return monolithic stack I, independent-stack I, and their ratio.

    Monolithic stack:
        n full-height H sections patterned in one part, with parallel-axis
        contribution around the centroid of the full stack.

    Separated stack:
        n full-height H instances patterned at spacing H, treated as
        non-composite independent sections with no global parallel-axis action.
    """

    i_single = h_inertia(geom.h, geom.b, geom.t1, geom.t2)
    area = h_area(geom.h, geom.b, geom.t1, geom.t2)
    centers = [(idx + 0.5) * geom.h for idx in range(geom.n_or_e)]
    stack_centroid = geom.n_or_e * geom.h / 2.0
    i_sep = geom.n_or_e * i_single
    i_mono = i_sep + area * sum((center - stack_centroid) ** 2 for center in centers)
    if not all(math.isfinite(value) and value > 0 for value in (i_mono, i_sep)):
        raise ValueError(f"invalid inertia values for {geom}: {i_mono}, {i_sep}")
    return i_mono, i_sep, i_mono / i_sep


def normalize(raw_ratio: float, inertia_ratio: float) -> float:
    if inertia_ratio < 1.0:
        raise ValueError(f"inertia ratio must be >= 1: {inertia_ratio}")
    if math.isclose(inertia_ratio, 1.0, rel_tol=0.0, abs_tol=1e-12):
        return raw_ratio
    return 1.0 + (raw_ratio - 1.0) / inertia_ratio


def dominates(raw_ratio: float, normalized_ratio: float) -> bool:
    return abs(normalized_ratio - 1.0) < 0.1 * abs(raw_ratio - 1.0)


def normalize_row(row: dict[str, str]) -> dict[str, str]:
    geom = parse_study_key(row["study_key"])
    raw = float(row["archive_peak_abs_rf2_ratio"])
    i_mono, i_sep, ratio = corrected_section_values(geom)
    normalized = normalize(raw, ratio)
    flag = dominates(raw, normalized)
    if geom.n_or_e == 1:
        note = "n_or_E=1 gives no section-stack correction; residual contrast is interface/contact/BC proxy"
    else:
        note = "full-height independent H stack corrected against monolithic stack parallel-axis inertia"
    return {
        "study_key": row["study_key"],
        "n_or_E": str(geom.n_or_e),
        "archive_peak_abs_rf2_ratio": f"{raw:.12g}",
        "i_eff_mono_mm4": f"{i_mono:.12g}",
        "i_eff_sep_mm4": f"{i_sep:.12g}",
        "i_eff_ratio_mono_over_sep": f"{ratio:.12g}",
        "normalized_rf2_ratio": f"{normalized:.12g}",
        "candidate_role": row.get("candidate_role", ""),
        "section_effect_dominates_flag": str(flag).lower(),
        "normalization_note": note,
        "i_eff_sep_model": (
            "full_height_H_instances_non_composite; "
            "I_sep=n*I_single(H,B,T1,T2); source-audited W3b"
        ),
        "source_basis": (
            "overall script: one Part with sketch linearPattern number2=E spacing2=A; "
            "separated script: LinearInstancePattern of full-height Part-1 instances spacing2=A plus contact sfricn"
        ),
    }


def run(anchor_links: Path, out: Path) -> tuple[int, int]:
    with anchor_links.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"empty anchor table: {anchor_links}")
    out_rows = [normalize_row(row) for row in rows]
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(out_rows)
    count = sum(row["section_effect_dominates_flag"] == "true" for row in out_rows)
    return len(out_rows), count


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Write source-audited W3b section normalization.")
    parser.add_argument("--anchor-links", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    n_rows, n_dominates = run(args.anchor_links, args.out)
    print(
        f"W3b corrected normalization wrote {n_rows} rows to {args.out}; "
        f"section_effect_dominates={n_dominates}/{n_rows}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
