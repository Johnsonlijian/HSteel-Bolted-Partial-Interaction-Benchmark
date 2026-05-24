"""Run the first non-Abaqus reduced-order phase-map sweep."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from .labels import LABEL_TO_CODE
from .reduced_member_model import MemberParams, run_member_case


def run_sweep() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for mu in [0.05, 0.10, 0.20, 0.35, 0.50]:
        for pressure_index in [0.30, 1.00, 2.50, 5.00, 10.00, 15.00]:
            for bolt_rows in [3, 5, 7]:
                for axial_ratio in [0.10, 0.25, 0.40, 0.55]:
                    for slenderness in [40.0, 60.0, 80.0]:
                        params = MemberParams(
                            mu=mu,
                            pressure_index=pressure_index,
                            bolt_rows=bolt_rows,
                            axial_ratio=axial_ratio,
                            slenderness=slenderness,
                        )
                        result = run_member_case(params)
                        rows.append(
                            {
                                "mu": mu,
                                "pressure_index": pressure_index,
                                "interface_capacity_index": mu * pressure_index,
                                "bolt_rows": bolt_rows,
                                "axial_ratio": axial_ratio,
                                "slenderness": slenderness,
                                "axial_slenderness_index": axial_ratio * slenderness / 60.0,
                                "peak_force": result["peak_force"],
                                "loop_energy": result["loop_energy"],
                                "energy_index": result["energy_index"],
                                "slip_index": result["slip_index"],
                                "mean_stick_fraction": result["mean_stick_fraction"],
                                "local_buckling_index": result["local_buckling_index"],
                                "global_instability_index": result["global_instability_index"],
                                "weak_state_label": result["weak_state_label"],
                            }
                        )
    return rows


def write_csv(rows: list[dict[str, object]], out_csv: Path) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_summary(rows: list[dict[str, object]], out_md: Path) -> None:
    labels: dict[str, int] = {}
    for row in rows:
        labels[str(row["weak_state_label"])] = labels.get(str(row["weak_state_label"]), 0) + 1
    total = len(rows)
    lines = [
        "# R03 Reduced-Order Sweep Summary",
        "",
        f"Total cases: {total}",
        "",
        "## Weak Response Labels",
        "",
        "| Label | Count | Share |",
        "| --- | ---: | ---: |",
    ]
    for label, count in sorted(labels.items(), key=lambda item: item[0]):
        lines.append(f"| {label} | {count} | {count / total:.3f} |")
    peak_values = np.asarray([float(r["peak_force"]) for r in rows])
    slip_values = np.asarray([float(r["slip_index"]) for r in rows])
    lines.extend(
        [
            "",
            "## Metric Ranges",
            "",
            f"- Peak force proxy: {peak_values.min():.4f} to {peak_values.max():.4f}",
            f"- Slip index: {slip_values.min():.4f} to {slip_values.max():.4f}",
            "",
            "## Interpretation Boundary",
            "",
            "This is a reduced-order PoC. The labels are screening labels, not validated physical failure modes.",
        ]
    )
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def plot_phase_map(rows: list[dict[str, object]], out_png: Path) -> None:
    subset = [r for r in rows if int(r["bolt_rows"]) == 5 and float(r["slenderness"]) == 60.0]
    x = np.asarray([float(r["interface_capacity_index"]) for r in subset])
    y = np.asarray([float(r["axial_slenderness_index"]) for r in subset])
    c = np.asarray([LABEL_TO_CODE[str(r["weak_state_label"])] for r in subset])

    fig, ax = plt.subplots(figsize=(7.2, 5.4), dpi=180)
    scatter = ax.scatter(x, y, c=c, cmap="tab10", s=85, edgecolors="black", linewidths=0.4)
    ax.set_xlabel("Interface capacity index, mu q_b")
    ax.set_ylabel("Axial-slenderness index, n L / 60")
    ax.set_title("R03 reduced-order phase map, bolt_rows=5, slenderness=60")
    ax.grid(True, alpha=0.28)
    handles = []
    labels = []
    for label, code in LABEL_TO_CODE.items():
        if code in set(c.tolist()):
            handles.append(plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=scatter.cmap(scatter.norm(code)), markeredgecolor="black", markersize=7))
            labels.append(label)
    ax.legend(handles, labels, loc="best", fontsize=7, frameon=True)
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)


def plot_example_hysteresis(out_png: Path) -> None:
    cases = [
        ("low interface", MemberParams(mu=0.05, pressure_index=0.30, bolt_rows=5, axial_ratio=0.10, slenderness=60.0)),
        ("medium interface", MemberParams(mu=0.20, pressure_index=1.00, bolt_rows=5, axial_ratio=0.25, slenderness=60.0)),
        ("high axial", MemberParams(mu=0.35, pressure_index=1.50, bolt_rows=5, axial_ratio=0.55, slenderness=80.0)),
    ]
    fig, ax = plt.subplots(figsize=(7.2, 5.4), dpi=180)
    for name, params in cases:
        result = run_member_case(params)
        ax.plot(result["drift"], result["force"], label=f"{name}: {result['weak_state_label']}")
    ax.set_xlabel("Drift proxy")
    ax.set_ylabel("Force proxy")
    ax.set_title("Reduced-order cyclic response examples")
    ax.grid(True, alpha=0.28)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", required=True)
    args = parser.parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    rows = run_sweep()
    write_csv(rows, outdir / "r03_reduced_order_sweep.csv")
    write_summary(rows, outdir / "r03_sweep_summary.md")
    plot_phase_map(rows, outdir / "r03_phase_map.png")
    plot_example_hysteresis(outdir / "r03_hysteresis_examples.png")


if __name__ == "__main__":
    main()
