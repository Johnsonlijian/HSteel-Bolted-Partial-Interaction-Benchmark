"""Bridge archive proxy cases to the reduced-order phase-map variables.

The bridge is provisional by design. It maps legacy archive descriptors to the
dimensionless reduced-order solver grid so we can decide which cases are useful
for calibration. It must not be described as a validated calibration.
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt

ARCHIVE_TO_AXIAL_RATIO = {
    1: 0.10,
    2: 0.25,
    3: 0.40,
}


def _float(row: dict[str, str], key: str, default: float = 0.0) -> float:
    value = row.get(key, "")
    if value in ("", None):
        return default
    return float(value)


def _int(row: dict[str, str], key: str, default: int = 0) -> int:
    value = row.get(key, "")
    if value in ("", None):
        return default
    return int(float(value))


def archive_mu(row: dict[str, str]) -> float:
    """Use the separated model's friction flag when the contrast is 0 vs 0.35."""

    contrast = row.get("sfricn_contrast", "")
    if "0.35" in contrast:
        return 0.35
    return 0.20


def archive_pressure_index(row: dict[str, str]) -> float:
    """Map the archive pbol flag to a dimensionless q_b index.

    The scaling is intentionally simple and visible: q_b = pbol / 30. This
    places the common archive value pbol=90 near q_b=3, inside the R03 sweep.
    """

    return max(0.30, _float(row, "pbol", 90.0) / 30.0)


def archive_axial_ratio(row: dict[str, str]) -> float:
    n_or_e = _int(row, "n_or_E", 1)
    return ARCHIVE_TO_AXIAL_RATIO.get(n_or_e, 0.55)


def archive_slenderness(row: dict[str, str]) -> float:
    """Return a provisional member slenderness index.

    The archive P1 cases have L/H around 30. R03's first sweep starts at 40, so
    we use the closest sweep level and keep the mismatch visible in the output.
    """

    h = max(_float(row, "H", 100.0), 1.0)
    length = _float(row, "L", 3000.0)
    return length / h


def nearest(value: float, grid: list[float]) -> float:
    return min(grid, key=lambda x: abs(x - value))


def response_direction_from_ratio(ratio: float) -> str:
    if ratio >= 1.20:
        return "archive_separated_higher"
    if ratio <= 0.80:
        return "archive_separated_lower"
    return "archive_near_neutral"


def trend_alignment(archive_direction: str, solver_label: str) -> str:
    """Coarse qualitative bridge between archive contrast and solver label."""

    if archive_direction == "archive_separated_higher":
        if solver_label in {"stiff_composite_like", "mixed_slip_stability"}:
            return "aligned_proxy"
        if solver_label == "slip_dominated":
            return "plausible_interface_sensitive"
        return "tension"
    if archive_direction == "archive_separated_lower":
        if solver_label in {"local_buckling_softening", "global_instability_sensitive", "slip_dominated"}:
            return "aligned_proxy"
        return "tension"
    if solver_label in {"mixed_slip_stability", "stiff_composite_like"}:
        return "aligned_proxy"
    return "plausible_interface_sensitive"


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return [{key.lstrip("\ufeff"): value for key, value in row.items()} for row in rows]


def build_bridge(archive_rows: list[dict[str, str]], sweep_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    mus = sorted({float(row["mu"]) for row in sweep_rows})
    pressures = sorted({float(row["pressure_index"]) for row in sweep_rows})
    bolt_rows_grid = sorted({int(float(row["bolt_rows"])) for row in sweep_rows})
    axial_grid = sorted({float(row["axial_ratio"]) for row in sweep_rows})
    slender_grid = sorted({float(row["slenderness"]) for row in sweep_rows})

    sweep_index = {
        (
            float(row["mu"]),
            float(row["pressure_index"]),
            int(float(row["bolt_rows"])),
            float(row["axial_ratio"]),
            float(row["slenderness"]),
        ): row
        for row in sweep_rows
    }

    bridged: list[dict[str, str]] = []
    for row in archive_rows:
        mu = nearest(archive_mu(row), mus)
        q_b_raw = archive_pressure_index(row)
        q_b = nearest(q_b_raw, pressures)
        bolt_rows = nearest(max(3, _int(row, "n_or_E", 1) + 2), bolt_rows_grid)
        axial_raw = archive_axial_ratio(row)
        axial = nearest(axial_raw, axial_grid)
        slender_raw = archive_slenderness(row)
        slender = nearest(slender_raw, slender_grid)

        solver = sweep_index[(mu, q_b, int(bolt_rows), axial, slender)]
        ratio = _float(row, "peak_abs_rf2_ratio_separated_overall", 1.0)
        archive_direction = response_direction_from_ratio(ratio)
        solver_label = solver["weak_state_label"]
        alignment = trend_alignment(archive_direction, solver_label)
        distance = math.sqrt(
            (archive_mu(row) - mu) ** 2
            + (q_b_raw - q_b) ** 2
            + (axial_raw - axial) ** 2
            + ((slender_raw - slender) / 40.0) ** 2
        )

        bridged.append(
            {
                "study_key": row["study_key"],
                "archive_peak_abs_rf2_ratio": f"{ratio:.6g}",
                "archive_response_direction": archive_direction,
                "archive_n_or_E": row.get("n_or_E", ""),
                "archive_nodedeform": row.get("nodedeform", ""),
                "mapped_mu_raw": f"{archive_mu(row):.6g}",
                "mapped_pressure_index_raw": f"{q_b_raw:.6g}",
                "mapped_axial_ratio_raw": f"{axial_raw:.6g}",
                "mapped_slenderness_raw": f"{slender_raw:.6g}",
                "nearest_mu": f"{mu:.6g}",
                "nearest_pressure_index": f"{q_b:.6g}",
                "nearest_bolt_rows": str(int(bolt_rows)),
                "nearest_axial_ratio": f"{axial:.6g}",
                "nearest_slenderness": f"{slender:.6g}",
                "solver_peak_force": solver["peak_force"],
                "solver_slip_index": solver["slip_index"],
                "solver_local_buckling_index": solver["local_buckling_index"],
                "solver_global_instability_index": solver["global_instability_index"],
                "solver_weak_state_label": solver_label,
                "trend_alignment": alignment,
                "mapping_distance": f"{distance:.6g}",
                "bridge_status": "screening_only_not_validated_calibration",
            }
        )
    return bridged


def write_csv(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_summary(rows: list[dict[str, str]], path: Path) -> None:
    labels = Counter(row["solver_weak_state_label"] for row in rows)
    alignments = Counter(row["trend_alignment"] for row in rows)
    lines = [
        "# R04 Archive-To-Reduced-Order Bridge Summary",
        "",
        f"Total archive proxy cases bridged: {len(rows)}",
        "",
        "## Solver Labels Assigned To Archive Proxy Cases",
        "",
        "| Solver weak label | Count |",
        "| --- | ---: |",
    ]
    for label, count in sorted(labels.items()):
        lines.append(f"| {label} | {count} |")
    lines.extend(
        [
            "",
            "## Trend Alignment",
            "",
            "| Alignment | Count |",
            "| --- | ---: |",
        ]
    )
    for label, count in sorted(alignments.items()):
        lines.append(f"| {label} | {count} |")
    lines.extend(
        [
            "",
            "## Interpretation Boundary",
            "",
            "This is a provisional bridge from archive proxy variables to R03 reduced-order variables. It is not a validated calibration. The bridge is useful for selecting calibration candidates and identifying variable mismatches.",
            "",
            "R04 diagnostic note: with the current descriptor-only mapping, all archive proxy cases land in `slip_dominated`. This does not mean all real cases are slip failures. It means the available archive descriptors are narrow in `sfricn/pbol`, so the bridge must next recover stronger physical variables such as direct slip, local buckling, contact output or a better stability index.",
            "",
            "## Mapping Rules",
            "",
            "- `sfricn=0_vs_0.35` -> `mu=0.35`.",
            "- `pbol` -> `pressure_index = pbol / 30`.",
            "- `n_or_E=1,2,3,>=4` -> `axial_ratio=0.10,0.25,0.40,0.55`.",
            "- `L/H` -> provisional slenderness, then nearest R03 grid level.",
            "- `n_or_E + 2` -> provisional bolt-row count, then nearest R03 grid level.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def candidate_role(row: dict[str, str]) -> str:
    direction = row["archive_response_direction"]
    ratio = float(row["archive_peak_abs_rf2_ratio"])
    if direction == "archive_separated_higher" and ratio >= 1.45:
        return "positive_interface_sensitivity_anchor"
    if direction == "archive_separated_lower" and ratio <= 0.65:
        return "negative_interface_sensitivity_anchor"
    if direction == "archive_near_neutral":
        return "transition_or_neutral_anchor"
    return "secondary_bridge_case"


def write_candidates(rows: list[dict[str, str]], path: Path) -> None:
    ranked = []
    for row in rows:
        ratio = float(row["archive_peak_abs_rf2_ratio"])
        rank_score = abs(math.log(max(ratio, 1e-9)))
        role = candidate_role(row)
        ranked.append(
            {
                "candidate_role": role,
                "rank_score": f"{rank_score:.6g}",
                "archive_peak_abs_rf2_ratio": row["archive_peak_abs_rf2_ratio"],
                "archive_response_direction": row["archive_response_direction"],
                "archive_n_or_E": row["archive_n_or_E"],
                "archive_nodedeform": row["archive_nodedeform"],
                "solver_weak_state_label": row["solver_weak_state_label"],
                "trend_alignment": row["trend_alignment"],
                "next_evidence_needed": "direct slip/local buckling/contact output or parameter-dictionary confirmation",
                "study_key": row["study_key"],
            }
        )
    ranked.sort(key=lambda r: (r["candidate_role"], -float(r["rank_score"])))
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(ranked[0].keys()))
        writer.writeheader()
        writer.writerows(ranked)


def plot_bridge(rows: list[dict[str, str]], path: Path) -> None:
    colors = {
        "aligned_proxy": "#2878b5",
        "plausible_interface_sensitive": "#f39b2f",
        "tension": "#c82423",
    }
    x = [float(row["archive_peak_abs_rf2_ratio"]) for row in rows]
    y = [float(row["solver_slip_index"]) for row in rows]
    c = [colors.get(row["trend_alignment"], "#555555") for row in rows]

    fig, ax = plt.subplots(figsize=(7.0, 5.2), dpi=180)
    ax.scatter(x, y, c=c, s=80, edgecolors="black", linewidths=0.45)
    ax.axvline(1.0, color="black", linewidth=0.8, linestyle="--", alpha=0.6)
    ax.set_xlabel("Archive separated/overall peak response proxy")
    ax.set_ylabel("R03 mapped slip index")
    ax.set_title("R04 provisional archive-to-reduced-order bridge")
    ax.grid(True, alpha=0.28)

    handles = [
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=color, markeredgecolor="black", label=label, markersize=7)
        for label, color in colors.items()
    ]
    ax.legend(handles=handles, fontsize=7, frameon=True)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive-cases", required=True)
    parser.add_argument("--sweep", required=True)
    parser.add_argument("--outdir", required=True)
    args = parser.parse_args()

    outdir = Path(args.outdir)
    rows = build_bridge(load_csv(Path(args.archive_cases)), load_csv(Path(args.sweep)))
    write_csv(rows, outdir / "r04_archive_solver_bridge.csv")
    write_candidates(rows, outdir / "r04_calibration_candidates.csv")
    write_summary(rows, outdir / "r04_bridge_summary.md")
    plot_bridge(rows, outdir / "r04_archive_solver_bridge.png")


if __name__ == "__main__":
    main()
