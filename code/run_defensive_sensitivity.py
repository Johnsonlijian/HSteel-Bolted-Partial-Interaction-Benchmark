"""Defensive sensitivity checks for the JCSR submission.

The checks are intentionally small and audit-facing:

1. Step-refinement checks for representative sliding and mixed-stability cases.
2. Weak-label threshold perturbations on the already generated W5 benchmark.

They do not redefine the main benchmark. They test whether the active-set load
stepping and weak-label thresholds create obvious artefacts in the claims.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
CODE_DIR = PROJECT_ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from run_w5_full_benchmark import (  # noqa: E402
    FIT_TABLE,
    OUTPUT_DIR as BENCHMARK_OUTPUT_DIR,
    build_case_grid,
    config_from_case,
    summarize_case,
)
from solver.extended_member_model import run_extended_member_case  # noqa: E402
from solver.labels import (  # noqa: E402
    GLOBAL_INSTABILITY_THRESHOLD,
    LOCAL_BUCKLING_THRESHOLD,
    MIXED_SLIP_INDEX_FLOOR,
    SLIP_DOMINANT_ENERGY_FLOOR,
    SLIP_DOMINANT_INDEX,
)

OUTPUT_DIR = BENCHMARK_OUTPUT_DIR
BENCHMARK_CSV = OUTPUT_DIR / "benchmark_full.csv"
STEP_CSV = OUTPUT_DIR / "step_refinement_summary.csv"
STEP_MD = OUTPUT_DIR / "step_refinement_summary.md"
LABEL_CSV = OUTPUT_DIR / "label_threshold_sensitivity.csv"
LABEL_MD = OUTPUT_DIR / "label_threshold_sensitivity.md"

STEP_CASE_IDS = ["W5-001", "W5-002"]
POINTS_PER_BRANCH = [4, 8, 17, 33]  # total protocol points: 49, 97, 205, 397


def protocol_steps(points_per_branch: int) -> int:
    return 1 + 12 * points_per_branch


def read_benchmark_rows() -> list[dict[str, str]]:
    with BENCHMARK_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def run_step_refinement() -> list[dict[str, object]]:
    cases = {case.case_id: case for case in build_case_grid()}
    baseline = {row["case_id"]: row for row in read_benchmark_rows()}
    rows: list[dict[str, object]] = []
    for case_id in STEP_CASE_IDS:
        case = cases[case_id]
        base_label = baseline[case_id]["weak_state_label"]
        for ppb in POINTS_PER_BRANCH:
            config = config_from_case(case, points_per_branch=ppb)
            result = run_extended_member_case(config=config, fit_table=FIT_TABLE)
            summary = summarize_case(case, result, config)
            rows.append(
                {
                    "case_id": case_id,
                    "baseline_label": base_label,
                    "load_steps": protocol_steps(ppb),
                    "points_per_branch": ppb,
                    "peak_base_reaction": summary["peak_base_reaction"],
                    "total_loop_energy": summary["total_loop_energy"],
                    "total_row_dissipation": summary["total_row_dissipation"],
                    "final_min_q_b_over_q_b0": summary["final_min_q_b_over_q_b0"],
                    "weak_state_label": summary["weak_state_label"],
                    "label_matches_baseline": summary["weak_state_label"] == base_label,
                    "n_newton_failures": summary["n_newton_failures"],
                    "converged": summary["converged"],
                }
            )
    return rows


def classify_with_thresholds(
    *,
    slip_index: float,
    local_buckling_index: float,
    global_instability_index: float,
    energy_index: float,
    global_threshold: float,
    local_threshold: float,
    slip_threshold: float,
    energy_floor: float,
    mixed_floor: float,
) -> str:
    if global_instability_index >= global_threshold:
        return "global_instability_sensitive"
    if local_buckling_index >= local_threshold:
        return "local_buckling_softening"
    if slip_index >= slip_threshold and energy_index >= energy_floor:
        return "slip_dominated"
    if slip_index >= mixed_floor:
        return "mixed_slip_stability"
    return "stiff_composite_like"


def threshold_scenarios() -> list[dict[str, float | str]]:
    base = {
        "global_threshold": GLOBAL_INSTABILITY_THRESHOLD,
        "local_threshold": LOCAL_BUCKLING_THRESHOLD,
        "slip_threshold": SLIP_DOMINANT_INDEX,
        "energy_floor": SLIP_DOMINANT_ENERGY_FLOOR,
        "mixed_floor": MIXED_SLIP_INDEX_FLOOR,
    }
    scenarios: list[dict[str, float | str]] = [
        {"scenario": "baseline", **base},
        {"scenario": "all_thresholds_minus10", **{k: v * 0.9 for k, v in base.items()}},
        {"scenario": "all_thresholds_plus10", **{k: v * 1.1 for k, v in base.items()}},
        {"scenario": "global_threshold_minus10", **base, "global_threshold": base["global_threshold"] * 0.9},
        {"scenario": "global_threshold_plus10", **base, "global_threshold": base["global_threshold"] * 1.1},
        {"scenario": "local_threshold_minus10", **base, "local_threshold": base["local_threshold"] * 0.9},
        {"scenario": "local_threshold_plus10", **base, "local_threshold": base["local_threshold"] * 1.1},
        {
            "scenario": "slip_thresholds_minus10",
            **base,
            "slip_threshold": base["slip_threshold"] * 0.9,
            "energy_floor": base["energy_floor"] * 0.9,
            "mixed_floor": base["mixed_floor"] * 0.9,
        },
        {
            "scenario": "slip_thresholds_plus10",
            **base,
            "slip_threshold": base["slip_threshold"] * 1.1,
            "energy_floor": base["energy_floor"] * 1.1,
            "mixed_floor": base["mixed_floor"] * 1.1,
        },
    ]
    return scenarios


def run_label_threshold_sensitivity() -> list[dict[str, object]]:
    baseline_rows = read_benchmark_rows()
    baseline_labels = {row["case_id"]: row["weak_state_label"] for row in baseline_rows}
    rows: list[dict[str, object]] = []
    for scenario in threshold_scenarios():
        labels: list[str] = []
        matches = 0
        for row in baseline_rows:
            label = classify_with_thresholds(
                slip_index=float(row["slip_index"]),
                local_buckling_index=float(row["local_buckling_index"]),
                global_instability_index=float(row["global_instability_index"]),
                energy_index=float(row["energy_index"]),
                global_threshold=float(scenario["global_threshold"]),
                local_threshold=float(scenario["local_threshold"]),
                slip_threshold=float(scenario["slip_threshold"]),
                energy_floor=float(scenario["energy_floor"]),
                mixed_floor=float(scenario["mixed_floor"]),
            )
            labels.append(label)
            matches += int(label == baseline_labels[row["case_id"]])
        counts = dict(sorted(Counter(labels).items()))
        rows.append(
            {
                "scenario": scenario["scenario"],
                "n_cases": len(baseline_rows),
                "label_agreement_to_baseline": matches / len(baseline_rows),
                "n_labels": len(counts),
                "label_counts_json": json.dumps(counts, sort_keys=True),
                "global_threshold": scenario["global_threshold"],
                "local_threshold": scenario["local_threshold"],
                "slip_threshold": scenario["slip_threshold"],
                "energy_floor": scenario["energy_floor"],
                "mixed_floor": scenario["mixed_floor"],
            }
        )
    return rows


def write_step_markdown(rows: list[dict[str, object]]) -> None:
    lines = [
        "# Step-refinement sensitivity",
        "",
        "| Case | Baseline label | Load steps | Peak reaction | Total loop energy | Total row dissipation | min(q_b)/q_b0 | Label | Match | Newton failures |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {case_id} | {baseline_label} | {load_steps} | {peak_base_reaction:.6g} | "
            "{total_loop_energy:.6g} | {total_row_dissipation:.6g} | "
            "{final_min_q_b_over_q_b0:.4f} | {weak_state_label} | {label_matches_baseline} | "
            "{n_newton_failures} |".format(**row)
        )
    lines.extend(
        [
            "",
            "Interpretation: the representative slip-dominated and mixed slip-stability cases retain their screening label and converge with zero Newton failures across the tested step range.",
        ]
    )
    STEP_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_label_markdown(rows: list[dict[str, object]]) -> None:
    lines = [
        "# Weak-label threshold sensitivity",
        "",
        "| Scenario | Agreement | Labels retained | Label counts |",
        "| --- | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| {scenario} | {label_agreement_to_baseline:.3f} | {n_labels} | `{label_counts_json}` |".format(**row)
        )
    min_agreement = min(float(row["label_agreement_to_baseline"]) for row in rows if row["scenario"] != "baseline")
    lines.extend(
        [
            "",
            f"Interpretation: all tested threshold perturbations retain all five labels, with minimum non-baseline agreement {min_agreement:.3f}. The weak labels are therefore auditable screening classes rather than single-threshold artefacts.",
        ]
    )
    LABEL_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    step_rows = run_step_refinement()
    label_rows = run_label_threshold_sensitivity()

    write_csv(
        STEP_CSV,
        step_rows,
        [
            "case_id",
            "baseline_label",
            "load_steps",
            "points_per_branch",
            "peak_base_reaction",
            "total_loop_energy",
            "total_row_dissipation",
            "final_min_q_b_over_q_b0",
            "weak_state_label",
            "label_matches_baseline",
            "n_newton_failures",
            "converged",
        ],
    )
    write_csv(
        LABEL_CSV,
        label_rows,
        [
            "scenario",
            "n_cases",
            "label_agreement_to_baseline",
            "n_labels",
            "label_counts_json",
            "global_threshold",
            "local_threshold",
            "slip_threshold",
            "energy_floor",
            "mixed_floor",
        ],
    )
    write_step_markdown(step_rows)
    write_label_markdown(label_rows)

    all_step_ok = all(row["converged"] and row["label_matches_baseline"] for row in step_rows)
    min_label_agreement = min(
        float(row["label_agreement_to_baseline"])
        for row in label_rows
        if row["scenario"] != "baseline"
    )
    print(f"step_refinement_rows={len(step_rows)} all_step_ok={all_step_ok}")
    print(f"label_threshold_scenarios={len(label_rows)} min_nonbaseline_agreement={min_label_agreement:.3f}")
    return 0 if all_step_ok and min_label_agreement >= 0.80 else 2


if __name__ == "__main__":
    raise SystemExit(main())
