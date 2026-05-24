from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]


def resolve_output_dir() -> Path:
    env_value = os.environ.get("HSTEEL_OUTPUT_DIR")
    if env_value:
        path = Path(env_value)
        return path if path.is_absolute() else ROOT / path
    public_outputs = ROOT / "outputs"
    if public_outputs.exists() and not (ROOT / "rounds").exists():
        return public_outputs
    return ROOT / "rounds" / "R06_path2_opensees_benchmark" / "outputs"


SUMMARY = resolve_output_dir() / "w13_sensitivity_summary.csv"
OUT = ROOT / "figures" / "fig5_sensitivity_ablation.png"


LABEL_ORDER = [
    "global_instability_sensitive",
    "local_buckling_softening",
    "slip_dominated",
    "mixed_slip_stability",
    "stiff_composite_like",
]

LABEL_COLORS = {
    "global_instability_sensitive": "#4C566A",
    "local_buckling_softening": "#B48EAD",
    "slip_dominated": "#D08770",
    "mixed_slip_stability": "#EBCB8B",
    "stiff_composite_like": "#A3BE8C",
}


def load_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with SUMMARY.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            row["n_cases"] = int(row["n_cases"])
            row["n_labels"] = int(row["n_labels"])
            row["label_agreement_to_baseline"] = float(row["label_agreement_to_baseline"])
            row["median_final_min_q_b_over_q_b0"] = float(row["median_final_min_q_b_over_q_b0"])
            row["median_total_row_dissipation"] = float(row["median_total_row_dissipation"])
            row["label_counts"] = json.loads(str(row["label_counts_json"]))
            rows.append(row)
    return rows


def short_name(name: str) -> str:
    return {
        "eta_0_no_relaxation": "eta=0",
        "eta_ds1_ci_lo": "ds1 CI lo",
        "eta_ds1_fit": "ds1 fit",
        "eta_ds1_ci_hi": "ds1 CI hi",
        "shape_outer_amplified": "outer\nbase",
        "shape_uniform": "uniform",
        "shape_outer_mild": "outer\nmild",
        "shape_center_amplified": "center\namp.",
    }.get(name, name)


def annotate_values(ax: plt.Axes, xs: np.ndarray, ys: list[float], fmt: str, dy: float = 0.02) -> None:
    for x, y in zip(xs, ys):
        ax.text(x, y + dy, fmt.format(y), ha="center", va="bottom", fontsize=8)


def main() -> None:
    rows = load_rows()
    eta_rows = [r for r in rows if r["scenario_group"] == "eta_envelope"]
    shape_rows = [r for r in rows if r["scenario_group"] == "row_shape"]

    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "legend.fontsize": 8,
            "figure.dpi": 140,
        }
    )
    fig = plt.figure(figsize=(10.5, 7.8))
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.15], hspace=0.42, wspace=0.28)
    ax_eta = fig.add_subplot(gs[0, 0])
    ax_shape = fig.add_subplot(gs[0, 1])
    ax_counts = fig.add_subplot(gs[1, :])

    # Panel A: eta envelope changes the internal preload state, not label topology.
    eta_x = np.arange(len(eta_rows))
    eta_q = [float(r["median_final_min_q_b_over_q_b0"]) for r in eta_rows]
    eta_labels = [int(r["n_labels"]) for r in eta_rows]
    ax_eta.bar(eta_x, eta_q, color="#5E81AC", width=0.68)
    ax_eta.set_xticks(eta_x, [short_name(str(r["scenario_name"])) for r in eta_rows])
    ax_eta.set_ylim(0, 1.12)
    ax_eta.set_ylabel("Median min(q_b/q_b0)")
    ax_eta.set_title("A. Preload-state sensitivity")
    ax_eta.grid(axis="y", color="#D8DEE9", linewidth=0.7)
    annotate_values(ax_eta, eta_x, eta_q, "{:.3f}", dy=0.025)
    ax_eta2 = ax_eta.twinx()
    ax_eta2.plot(eta_x, eta_labels, color="#2E3440", marker="o", linewidth=1.4)
    ax_eta2.set_ylim(0, 6)
    ax_eta2.set_ylabel("No. of labels")
    ax_eta2.set_yticks(range(0, 7))

    # Panel B: row-shape perturbations and label agreement.
    shape_x = np.arange(len(shape_rows))
    agreement = [float(r["label_agreement_to_baseline"]) for r in shape_rows]
    n_labels = [int(r["n_labels"]) for r in shape_rows]
    colors = ["#5E81AC" if i == 0 else "#88C0D0" for i in range(len(shape_rows))]
    ax_shape.bar(shape_x, agreement, color=colors, width=0.68)
    ax_shape.set_xticks(shape_x, [short_name(str(r["scenario_name"])) for r in shape_rows])
    ax_shape.set_ylim(0, 1.08)
    ax_shape.set_ylabel("Label agreement to baseline")
    ax_shape.set_title("B. Row-slip map sensitivity")
    ax_shape.grid(axis="y", color="#D8DEE9", linewidth=0.7)
    annotate_values(ax_shape, shape_x, agreement, "{:.3f}", dy=0.025)
    for x, n in zip(shape_x, n_labels):
        ax_shape.text(x, 0.06, f"{n} labels", ha="center", va="bottom", fontsize=8, color="#2E3440")

    # Panel C: label-count robustness under row-shape perturbation.
    bottoms = np.zeros(len(shape_rows))
    for label in LABEL_ORDER:
        counts = [int(dict(r["label_counts"]).get(label, 0)) for r in shape_rows]
        ax_counts.bar(
            shape_x,
            counts,
            bottom=bottoms,
            color=LABEL_COLORS[label],
            width=0.62,
            label=label.replace("_", " "),
        )
        bottoms += np.array(counts)
    ax_counts.set_xticks(shape_x, [short_name(str(r["scenario_name"])) for r in shape_rows])
    ax_counts.set_ylabel("Cases per weak response label")
    ax_counts.set_title("C. Label-count structure under row-shape alternatives")
    ax_counts.set_ylim(0, 100)
    ax_counts.grid(axis="y", color="#D8DEE9", linewidth=0.7)
    ax_counts.legend(ncols=3, loc="upper center", bbox_to_anchor=(0.5, -0.20), frameon=False)

    fig.suptitle(
        "W13 sensitivity and ablation checks",
        fontsize=12,
        fontweight="bold",
        y=0.98,
    )
    fig.text(0.5, 0.945, "All 720 cases converged; label topology remains bounded by the tested assumptions.", ha="center", fontsize=9, color="#4C566A")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, bbox_inches="tight", dpi=220)
    plt.close(fig)
    print(OUT)


if __name__ == "__main__":
    main()
