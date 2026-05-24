"""Create the main-text response-state map for the JCSR submission."""

from __future__ import annotations

import csv
import os
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]


def resolve_output_dir() -> Path:
    env_value = os.environ.get("HSTEEL_OUTPUT_DIR")
    if env_value:
        path = Path(env_value)
        return path if path.is_absolute() else ROOT / path
    public_outputs = ROOT / "outputs"
    if public_outputs.exists() and not (ROOT / "rounds").exists():
        return public_outputs
    return ROOT / "rounds/R06_path2_opensees_benchmark/outputs"


INPUT = resolve_output_dir() / "benchmark_full.csv"
OUTPUT = ROOT / "figures/fig4_response_state_map.png"

LABEL_ORDER = [
    "stiff_composite_like",
    "slip_dominated",
    "local_buckling_softening",
    "global_instability_sensitive",
    "mixed_slip_stability",
]
LABEL_TEXT = {
    "stiff_composite_like": "stiff composite-like",
    "slip_dominated": "slip dominated",
    "local_buckling_softening": "local buckling softening",
    "global_instability_sensitive": "global instability sensitive",
    "mixed_slip_stability": "mixed slip-stability",
}
COLORS = {
    "stiff_composite_like": "#3b7ddd",
    "slip_dominated": "#c4413a",
    "local_buckling_softening": "#d8a03b",
    "global_instability_sensitive": "#6b57a8",
    "mixed_slip_stability": "#3a8f68",
}
MARKERS = {
    "small_H80_B80_T1-5_T2-7": "o",
    "medium_H100_B100_T1-6_T2-8": "s",
    "large_H140_B140_T1-8_T2-12": "^",
}
SLICE_TEXT = {
    "small_H80_B80_T1-5_T2-7": "small slice",
    "medium_H100_B100_T1-6_T2-8": "medium slice",
    "large_H140_B140_T1-8_T2-12": "large slice",
}


def load_rows() -> list[dict[str, str]]:
    with INPUT.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    rows = load_rows()
    by_slice: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_slice[row["ieff_slice"]].append(row)

    fig, axes = plt.subplots(
        1,
        2,
        figsize=(12.8, 5.2),
        gridspec_kw={"width_ratios": [1.25, 1.0]},
        constrained_layout=True,
    )
    ax_map, ax_bar = axes

    for label in LABEL_ORDER:
        for slice_name, slice_rows in by_slice.items():
            xs = [
                float(row["slip_index"])
                for row in slice_rows
                if row["weak_state_label"] == label
            ]
            ys = [
                float(row["global_instability_index"])
                for row in slice_rows
                if row["weak_state_label"] == label
            ]
            if not xs:
                continue
            ax_map.scatter(
                xs,
                ys,
                s=52,
                marker=MARKERS.get(slice_name, "o"),
                color=COLORS[label],
                edgecolor="#202020",
                linewidth=0.35,
                alpha=0.88,
            )

    ax_map.set_xlabel("Slip index")
    ax_map.set_ylabel("Global-instability index")
    ax_map.set_title("(a) Response-state map")
    ax_map.grid(True, color="#d9d9d9", linewidth=0.6, alpha=0.75)

    label_handles = [
        plt.Line2D(
            [0],
            [0],
            marker="o",
            linestyle="",
            markersize=7,
            markerfacecolor=COLORS[label],
            markeredgecolor="#202020",
            label=LABEL_TEXT[label],
        )
        for label in LABEL_ORDER
    ]
    slice_handles = [
        plt.Line2D(
            [0],
            [0],
            marker=marker,
            linestyle="",
            markersize=7,
            markerfacecolor="white",
            markeredgecolor="#202020",
            label=SLICE_TEXT.get(slice_name, slice_name),
        )
        for slice_name, marker in MARKERS.items()
    ]
    leg1 = ax_map.legend(
        handles=label_handles,
        title="Weak response class",
        loc="upper left",
        bbox_to_anchor=(0.01, 0.99),
        fontsize=8.1,
        title_fontsize=8.4,
        frameon=True,
    )
    ax_map.add_artist(leg1)
    ax_map.legend(
        handles=slice_handles,
        title="Fixed section slice",
        loc="lower right",
        fontsize=8.1,
        title_fontsize=8.4,
        frameon=True,
    )

    slices = sorted(by_slice, key=lambda name: int(by_slice[name][0]["slice_order"]))
    bottoms = [0] * len(slices)
    for label in LABEL_ORDER:
        values = []
        for slice_name in slices:
            counts = Counter(row["weak_state_label"] for row in by_slice[slice_name])
            values.append(counts[label])
        ax_bar.bar(
            [SLICE_TEXT.get(slice_name, slice_name) for slice_name in slices],
            values,
            bottom=bottoms,
            color=COLORS[label],
            edgecolor="white",
            linewidth=0.7,
            label=LABEL_TEXT[label],
        )
        bottoms = [base + value for base, value in zip(bottoms, values)]

    ax_bar.set_ylabel("Number of cases")
    ax_bar.set_title("(b) Label coverage by fixed section")
    ax_bar.set_ylim(0, max(bottoms) * 1.14)
    ax_bar.grid(True, axis="y", color="#d9d9d9", linewidth=0.6, alpha=0.75)
    for idx, total in enumerate(bottoms):
        ax_bar.text(idx, total + 0.8, str(total), ha="center", va="bottom", fontsize=9)

    fig.suptitle(
        "Ninety-case screening map at fixed effective-section slices",
        fontsize=13,
        fontweight="bold",
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT, dpi=300)
    plt.close(fig)
    print(OUTPUT)


if __name__ == "__main__":
    main()
