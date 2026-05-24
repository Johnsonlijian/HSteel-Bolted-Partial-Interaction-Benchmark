"""Generate Figure 6: archive response-proxy cross-check.

The plot uses only the corrected, source-audited derived table from W3b.
It is intentionally a response-proxy figure: it visualizes section-effect
normalization and highlights the n_or_E=1 anchors where inertia correction is
unity, but it does not imply direct bolt-force or inter-limb slip validation.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRIVATE_INPUT_CSV = (
    PROJECT_ROOT
    / "rounds"
    / "R06_path2_opensees_benchmark"
    / "outputs"
    / "archive_section_normalized_w3b_corrected.csv"
)
PUBLIC_INPUT_CSV = PROJECT_ROOT / "outputs" / "archive_section_normalized_w3b_corrected.csv"
INPUT_CSV = PRIVATE_INPUT_CSV if PRIVATE_INPUT_CSV.exists() else PUBLIC_INPUT_CSV
OUTPUT_PNG = PROJECT_ROOT / "figures" / "fig6_archive_response_proxy.png"


def main() -> None:
    df = pd.read_csv(INPUT_CSV)
    df = df.sort_values(["n_or_E", "archive_peak_abs_rf2_ratio"]).reset_index(drop=True)

    single = df["n_or_E"] == 1
    multi = ~single

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.labelsize": 11,
            "axes.titlesize": 12,
            "legend.fontsize": 9,
            "figure.dpi": 160,
        }
    )

    fig, axes = plt.subplots(1, 2, figsize=(12.2, 4.8), constrained_layout=True)

    ax = axes[0]
    ax.axhline(1.0, color="#777777", lw=1.0, ls="--", zorder=0)
    ax.axvline(1.0, color="#777777", lw=1.0, ls="--", zorder=0)
    ax.scatter(
        df.loc[multi, "i_eff_ratio_mono_over_sep"],
        df.loc[multi, "archive_peak_abs_rf2_ratio"],
        s=64,
        color="#3b6ea8",
        edgecolor="white",
        linewidth=0.8,
        label="multi-H archive anchors",
        zorder=3,
    )
    ax.scatter(
        df.loc[single, "i_eff_ratio_mono_over_sep"],
        df.loc[single, "archive_peak_abs_rf2_ratio"],
        s=84,
        marker="D",
        color="#c44e52",
        edgecolor="white",
        linewidth=0.8,
        label="n_or_E = 1 anchors",
        zorder=4,
    )
    ax.set_xscale("log")
    ax.set_xlabel(r"Section-effect ratio $I_\mathrm{mono}/I_\mathrm{sep}$")
    ax.set_ylabel("Archive peak |RF2| ratio")
    ax.set_title("Response contrast before normalization")
    ax.legend(frameon=False, loc="best")
    ax.grid(True, which="both", color="#dddddd", lw=0.6, alpha=0.8)

    ax = axes[1]
    colors = df["n_or_E"].map(lambda n: "#c44e52" if n == 1 else "#3b6ea8")
    y = range(len(df))
    ax.barh(y, df["normalized_rf2_ratio"], color=colors, alpha=0.9)
    ax.axvline(1.0, color="#555555", lw=1.0, ls="--")
    ax.set_yticks(list(y))
    ax.set_yticklabels([f"n={int(n)}" for n in df["n_or_E"]])
    ax.set_xlabel("Normalized response ratio")
    ax.set_title("After source-audited section normalization")
    ax.grid(True, axis="x", color="#dddddd", lw=0.6, alpha=0.8)

    for idx, row in df.iterrows():
        label = "clean proxy" if row["n_or_E"] == 1 else "section-corrected"
        ax.text(
            row["normalized_rf2_ratio"] + 0.03,
            idx,
            label,
            va="center",
            fontsize=8,
            color="#333333",
        )

    fig.suptitle(
        "Archive-derived response-proxy check: section normalization and residual interface sensitivity",
        y=1.03,
        fontsize=13,
    )
    fig.savefig(OUTPUT_PNG, dpi=300, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
