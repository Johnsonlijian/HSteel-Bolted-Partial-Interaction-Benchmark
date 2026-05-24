"""Run W13 sensitivity checks for the bounded-screening manuscript.

The analysis answers two reviewer-facing questions:

1. Are trends dominated by the fitted relaxation decay parameter, or do the
   response classes persist across an eta_dis envelope?
2. Are conclusions an artifact of the assumed row-slip shape map?

The script reuses the W5 case grid and the imported extended member solver. It
does not create new raw data and does not alter the W5 benchmark outputs.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
CODE_DIR = PROJECT_ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from run_w5_full_benchmark import (  # noqa: E402
    BASE_COLUMNS,
    FIT_TABLE,
    build_case_grid,
    config_from_case,
    summarize_case,
)
from solver.extended_member_model import run_extended_member_case  # noqa: E402


def resolve_output_dir() -> Path:
    env_value = os.environ.get("HSTEEL_OUTPUT_DIR")
    if env_value:
        path = Path(env_value)
        return path if path.is_absolute() else PROJECT_ROOT / path
    public_outputs = PROJECT_ROOT / "outputs"
    if public_outputs.exists() and not (PROJECT_ROOT / "rounds").exists():
        return public_outputs
    return PROJECT_ROOT / "rounds" / "R06_path2_opensees_benchmark" / "outputs"


OUTPUT_DIR = resolve_output_dir()
CASE_CSV = OUTPUT_DIR / "w13_sensitivity_case_summary.csv"
SUMMARY_CSV = OUTPUT_DIR / "w13_sensitivity_summary.csv"
TABLE_MD = OUTPUT_DIR / "w13_sensitivity_table.md"
FIGURE_PNG = OUTPUT_DIR / "w13_sensitivity_figure.png"

SCENARIO_COLUMNS = [
    "scenario_group",
    "scenario_name",
    "eta_dis",
    "row_shape_profile",
    "n_cases",
    "n_converged",
    "n_failed",
    "n_labels",
    "label_counts_json",
    "label_agreement_to_baseline",
    "median_final_min_q_b_over_q_b0",
    "median_total_row_dissipation",
    "median_slip_index",
    "median_peak_base_reaction",
]

CASE_COLUMNS = [
    "scenario_group",
    "scenario_name",
    "eta_dis",
    "row_shape_profile",
    *BASE_COLUMNS,
]


def load_ds1_fit() -> dict[str, float]:
    with FIT_TABLE.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["dataset_id"] == "ds1_eraliev2021_m12_120c":
                return {
                    "eta": float(row["eta_dis"]),
                    "eta_lo": float(row["eta_dis_ci_lo"]),
                    "eta_hi": float(row["eta_dis_ci_hi"]),
                    "q_res": float(row["q_b_residual"]),
                }
    raise ValueError(f"ds1 row not found in {FIT_TABLE}")


def scenarios() -> list[dict[str, object]]:
    fit = load_ds1_fit()
    return [
        {
            "scenario_group": "eta_envelope",
            "scenario_name": "eta_0_no_relaxation",
            "eta_dis": 0.0,
            "row_shape_profile": "outer_amplified",
        },
        {
            "scenario_group": "eta_envelope",
            "scenario_name": "eta_ds1_ci_lo",
            "eta_dis": fit["eta_lo"],
            "row_shape_profile": "outer_amplified",
        },
        {
            "scenario_group": "eta_envelope",
            "scenario_name": "eta_ds1_fit",
            "eta_dis": fit["eta"],
            "row_shape_profile": "outer_amplified",
        },
        {
            "scenario_group": "eta_envelope",
            "scenario_name": "eta_ds1_ci_hi",
            "eta_dis": fit["eta_hi"],
            "row_shape_profile": "outer_amplified",
        },
        {
            "scenario_group": "row_shape",
            "scenario_name": "shape_outer_amplified",
            "eta_dis": fit["eta"],
            "row_shape_profile": "outer_amplified",
        },
        {
            "scenario_group": "row_shape",
            "scenario_name": "shape_uniform",
            "eta_dis": fit["eta"],
            "row_shape_profile": "uniform",
        },
        {
            "scenario_group": "row_shape",
            "scenario_name": "shape_outer_mild",
            "eta_dis": fit["eta"],
            "row_shape_profile": "outer_mild",
        },
        {
            "scenario_group": "row_shape",
            "scenario_name": "shape_center_amplified",
            "eta_dis": fit["eta"],
            "row_shape_profile": "center_amplified",
        },
    ]


def run_sensitivity() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    cases = build_case_grid()
    for scenario in scenarios():
        for case in cases:
            config = config_from_case(case, points_per_branch=30)
            config = replace(
                config,
                eta_dis=float(scenario["eta_dis"]),
                row_shape_profile=str(scenario["row_shape_profile"]),
            )
            result = run_extended_member_case(config=config, fit_table=FIT_TABLE)
            row = summarize_case(case, result, config)
            rows.append(
                {
                    "scenario_group": scenario["scenario_group"],
                    "scenario_name": scenario["scenario_name"],
                    "eta_dis": scenario["eta_dis"],
                    "row_shape_profile": scenario["row_shape_profile"],
                    **row,
                }
            )
    return rows


def write_csv(rows: list[dict[str, object]], path: Path, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def aggregate(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    baseline = {
        row["case_id"]: row["weak_state_label"]
        for row in rows
        if row["scenario_name"] == "eta_ds1_fit"
    }
    summary_rows: list[dict[str, object]] = []
    for scenario in scenarios():
        selected = [row for row in rows if row["scenario_name"] == scenario["scenario_name"]]
        labels = [str(row["weak_state_label"]) for row in selected]
        counts = {label: labels.count(label) for label in sorted(set(labels))}
        agreement = float(
            np.mean(
                [
                    1.0 if str(row["weak_state_label"]) == baseline[row["case_id"]] else 0.0
                    for row in selected
                ]
            )
        )
        summary_rows.append(
            {
                "scenario_group": scenario["scenario_group"],
                "scenario_name": scenario["scenario_name"],
                "eta_dis": scenario["eta_dis"],
                "row_shape_profile": scenario["row_shape_profile"],
                "n_cases": len(selected),
                "n_converged": sum(bool(row["converged"]) for row in selected),
                "n_failed": sum(not bool(row["converged"]) for row in selected),
                "n_labels": len(counts),
                "label_counts_json": json.dumps(counts, sort_keys=True),
                "label_agreement_to_baseline": agreement,
                "median_final_min_q_b_over_q_b0": float(
                    np.median([float(row["final_min_q_b_over_q_b0"]) for row in selected])
                ),
                "median_total_row_dissipation": float(
                    np.median([float(row["total_row_dissipation"]) for row in selected])
                ),
                "median_slip_index": float(
                    np.median([float(row["slip_index"]) for row in selected])
                ),
                "median_peak_base_reaction": float(
                    np.median([float(row["peak_base_reaction"]) for row in selected])
                ),
            }
        )
    return summary_rows


def write_table(summary_rows: list[dict[str, object]], path: Path) -> None:
    lines = [
        "# W13 Sensitivity Summary",
        "",
        "This table supports the JCSR-positioned claim that the framework is a bounded reduced-order screening benchmark, not a design-ready prediction model.",
        "",
        "## Scenario Summary",
        "",
        "| Scenario | Group | Converged | Labels | Agreement vs baseline | Median min q_b/q_b0 | Median slip index | Label counts |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in summary_rows:
        lines.append(
            "| {scenario_name} | {scenario_group} | {n_converged}/{n_cases} | {n_labels} | "
            "{label_agreement_to_baseline:.3f} | {median_final_min_q_b_over_q_b0:.3f} | "
            "{median_slip_index:.3f} | `{label_counts_json}` |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `eta_dis = 0` is the no-relaxation ablation; contrasts with ds1 CI scenarios isolate the contribution of dissipation-driven preload decay.",
            "- Row-shape scenarios test whether the weak response classes are an artifact of the baseline outer-row-amplified slip map.",
            "- The analysis should be cited as sensitivity evidence only. It does not convert the model into a design-ready predictor.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_figure(summary_rows: list[dict[str, object]], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = sorted(
        {
            label
            for row in summary_rows
            for label in json.loads(str(row["label_counts_json"])).keys()
        }
    )
    palette = {
        "global_instability_sensitive": "#2f6f4e",
        "local_buckling_softening": "#d79a2b",
        "mixed_slip_stability": "#7a5195",
        "slip_dominated": "#b0442e",
        "stiff_composite_like": "#3f6f9f",
    }
    fig, axes = plt.subplots(1, 2, figsize=(12.2, 4.8), dpi=160)

    for ax, group in zip(axes, ["eta_envelope", "row_shape"]):
        selected = [row for row in summary_rows if row["scenario_group"] == group]
        x = np.arange(len(selected))
        bottom = np.zeros(len(selected))
        for label in labels:
            values = np.array(
                [json.loads(str(row["label_counts_json"])).get(label, 0) for row in selected],
                dtype=float,
            )
            ax.bar(x, values, bottom=bottom, color=palette.get(label, "#777777"), label=label.replace("_", " "))
            bottom += values
        ax.set_xticks(x, [str(row["scenario_name"]).replace("_", "\n") for row in selected], fontsize=7)
        ax.set_ylabel("Case count")
        ax.set_title(group.replace("_", " ").title())
        ax.set_ylim(0, 90)
    axes[1].legend(frameon=False, fontsize=7, bbox_to_anchor=(1.02, 1), loc="upper left")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)


def main() -> int:
    rows = run_sensitivity()
    summary_rows = aggregate(rows)
    write_csv(rows, CASE_CSV, CASE_COLUMNS)
    write_csv(summary_rows, SUMMARY_CSV, SCENARIO_COLUMNS)
    write_table(summary_rows, TABLE_MD)
    write_figure(summary_rows, FIGURE_PNG)
    all_converged = all(bool(row["converged"]) for row in rows)
    min_labels = min(int(row["n_labels"]) for row in summary_rows)
    print(f"w13_cases={len(rows)}")
    print(f"w13_scenarios={len(summary_rows)}")
    print(f"w13_all_converged={all_converged}")
    print(f"w13_min_labels={min_labels}")
    print(f"w13_outputs={CASE_CSV};{SUMMARY_CSV};{TABLE_MD};{FIGURE_PNG}")
    return 0 if all_converged and min_labels >= 3 else 2


if __name__ == "__main__":
    raise SystemExit(main())
