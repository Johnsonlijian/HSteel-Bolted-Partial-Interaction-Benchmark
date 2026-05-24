"""Run the W5 full fixed-I_eff benchmark.

W5 expands the W4 first-slice sweep to three fixed-section slices. Each slice
keeps its H-section geometry constant while interface and stability parameters
vary, so within-slice contrasts are not caused by changing effective section
inertia.
"""

from __future__ import annotations

import csv
import json
import math
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from solver.extended_member_model import (  # noqa: E402
    ExtendedMemberConfig,
    h_section_properties,
    run_extended_member_case,
)
from solver.labels import classify_response  # noqa: E402


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
FIT_TABLE = OUTPUT_DIR / "relaxation_fit_table.csv"

BENCHMARK_CSV = OUTPUT_DIR / "benchmark_full.csv"
HISTORY_CSV = OUTPUT_DIR / "benchmark_full_history.csv"
SUMMARY_JSON = OUTPUT_DIR / "benchmark_full_summary.json"
FIGURE_PNG = OUTPUT_DIR / "benchmark_full_figure4.png"


BASE_COLUMNS = [
    "case_id",
    "ieff_slice",
    "slice_order",
    "h",
    "b",
    "t1",
    "t2",
    "i_single",
    "i_sep",
    "i_mono",
    "length",
    "slenderness",
    "mu",
    "q_b0",
    "bolt_rows",
    "axial_ratio",
    "k_stick",
    "peak_base_reaction",
    "total_loop_energy",
    "total_row_dissipation",
    "final_min_q_b",
    "final_mean_q_b",
    "final_min_q_b_over_q_b0",
    "rows_relaxed",
    "composite_factor_final",
    "max_abs_row_slip",
    "slip_index",
    "local_buckling_index",
    "global_instability_index",
    "energy_index",
    "weak_state_label",
    "n_newton_iterations_total",
    "n_newton_failures",
    "converged",
]


HISTORY_COLUMNS = [
    "case_id",
    "ieff_slice",
    "weak_state_label",
    "step",
    "time_or_drift",
    "applied_displacement",
    "base_reaction",
    "row_idx",
    "row_slip",
    "row_connector_force",
    "row_dissipation_increment",
    "row_q_b",
    "row_sticking_flag",
]


@dataclass(frozen=True)
class SectionSlice:
    name: str
    order: int
    h: float
    b: float
    t1: float
    t2: float
    baseline_length: float


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    section: SectionSlice
    slenderness: float
    mu: float
    q_b0: float
    bolt_rows: int
    axial_ratio: float


def section_slices() -> list[SectionSlice]:
    return [
        SectionSlice("small_H80_B80_T1-5_T2-7", 1, 80.0, 80.0, 5.0, 7.0, 2400.0),
        SectionSlice("medium_H100_B100_T1-6_T2-8", 2, 100.0, 100.0, 6.0, 8.0, 3000.0),
        SectionSlice("large_H140_B140_T1-8_T2-12", 3, 140.0, 140.0, 8.0, 12.0, 4200.0),
    ]


def build_case_grid() -> list[BenchmarkCase]:
    axial_slender_pairs = [
        (0.10, 35.0),
        (0.25, 55.0),
        (0.40, 75.0),
        (0.55, 95.0),
        (0.70, 115.0),
    ]
    interface_pairs = [
        (0.20, 0.70),
        (0.35, 1.00),
        (0.55, 1.30),
    ]
    cases: list[BenchmarkCase] = []
    counter = 1
    for section in section_slices():
        for axial_ratio, slenderness in axial_slender_pairs:
            for bolt_rows in (3, 5):
                for mu, q_b0 in interface_pairs:
                    cases.append(
                        BenchmarkCase(
                            case_id=f"W5-{counter:03d}",
                            section=section,
                            slenderness=slenderness,
                            mu=mu,
                            q_b0=q_b0,
                            bolt_rows=bolt_rows,
                            axial_ratio=axial_ratio,
                        )
                    )
                    counter += 1
    return cases


def config_from_case(case: BenchmarkCase, *, points_per_branch: int = 30) -> ExtendedMemberConfig:
    length = case.section.baseline_length * math.sqrt(case.slenderness / 55.0)
    return ExtendedMemberConfig(
        length=length,
        h=case.section.h,
        b=case.section.b,
        t1=case.section.t1,
        t2=case.section.t2,
        mu=case.mu,
        q_b0=case.q_b0,
        n_bolt_rows=case.bolt_rows,
        axial_ratio=case.axial_ratio,
        points_per_branch=points_per_branch,
        p_delta_active=True,
    )


def _local_buckling_index(config: ExtendedMemberConfig, slenderness: float) -> float:
    base = 0.028
    slender_factor = max(0.35, 70.0 / max(slenderness, 1.0))
    axial_factor = max(0.25, 1.0 - 0.65 * config.axial_ratio)
    row_factor = 1.0 + 0.035 * max(0, config.n_bolt_rows - 3)
    delta_lb = base * slender_factor * axial_factor * row_factor
    return max(0.0, config.max_drift / max(delta_lb, 1e-12) - 1.0)


def summarize_case(
    case: BenchmarkCase,
    result: dict[str, object],
    config: ExtendedMemberConfig,
) -> dict[str, object]:
    history = result["history"]
    summary = result["summary"]
    section = h_section_properties(config)
    max_abs_slip = max(abs(float(row["row_slip"])) for row in history)
    yield_slip = config.mu * config.q_b0 / max(config.k_stick, 1e-12)
    slip_index = max_abs_slip / max(yield_slip, 1e-12)
    peak = float(summary["peak_base_reaction"])
    loop_energy = float(summary["total_loop_energy"])
    max_displacement = config.max_drift * config.length
    energy_index = loop_energy / max(abs(peak) * max_displacement, 1e-12)
    local_index = _local_buckling_index(config, case.slenderness)
    global_index = config.axial_ratio * case.slenderness / 52.0
    weak_label = classify_response(
        slip_index=slip_index,
        local_buckling_index=local_index,
        global_instability_index=global_index,
        energy_index=energy_index,
    )
    final_q = [float(q) for q in summary["per_row_final_q_b"]]
    total_dissipation = float(sum(summary["per_row_cumulative_dissipation"]))
    converged = int(summary["n_newton_failures"]) == 0
    final_min = min(final_q)

    return {
        "case_id": case.case_id,
        "ieff_slice": case.section.name,
        "slice_order": case.section.order,
        "h": config.h,
        "b": config.b,
        "t1": config.t1,
        "t2": config.t2,
        "i_single": section.i_single,
        "i_sep": section.i_sep,
        "i_mono": section.i_mono,
        "length": config.length,
        "slenderness": case.slenderness,
        "mu": config.mu,
        "q_b0": config.q_b0,
        "bolt_rows": config.n_bolt_rows,
        "axial_ratio": config.axial_ratio,
        "k_stick": config.k_stick,
        "peak_base_reaction": peak,
        "total_loop_energy": loop_energy,
        "total_row_dissipation": total_dissipation,
        "final_min_q_b": final_min,
        "final_mean_q_b": float(np.mean(final_q)),
        "final_min_q_b_over_q_b0": final_min / config.q_b0,
        "rows_relaxed": int(sum(q < config.q_b0 - 1e-9 for q in final_q)),
        "composite_factor_final": float(summary["composite_factor_final"]),
        "max_abs_row_slip": max_abs_slip,
        "slip_index": slip_index,
        "local_buckling_index": local_index,
        "global_instability_index": global_index,
        "energy_index": energy_index,
        "weak_state_label": weak_label,
        "n_newton_iterations_total": int(summary["n_newton_iterations_total"]),
        "n_newton_failures": int(summary["n_newton_failures"]),
        "converged": converged,
    }


def run_benchmark(*, points_per_branch: int = 30) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    rows: list[dict[str, object]] = []
    history_rows: list[dict[str, object]] = []
    for case in build_case_grid():
        config = config_from_case(case, points_per_branch=points_per_branch)
        result = run_extended_member_case(config=config, fit_table=FIT_TABLE)
        summary_row = summarize_case(case, result, config)
        rows.append(summary_row)
        for hist_row in result["history"]:
            history_rows.append(
                {
                    "case_id": case.case_id,
                    "ieff_slice": case.section.name,
                    "weak_state_label": summary_row["weak_state_label"],
                    **hist_row,
                }
            )
    return rows, history_rows


def write_csv(rows: list[dict[str, object]], path: Path, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def _slice_label_counts(rows: list[dict[str, object]]) -> dict[str, dict[str, int]]:
    grouped: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        grouped[str(row["ieff_slice"])][str(row["weak_state_label"])] += 1
    return {
        slice_name: dict(sorted(counter.items()))
        for slice_name, counter in sorted(grouped.items())
    }


def write_summary_json(rows: list[dict[str, object]], path: Path) -> None:
    counts = Counter(str(row["weak_state_label"]) for row in rows)
    slice_counts = _slice_label_counts(rows)
    payload = {
        "n_cases": len(rows),
        "n_converged": sum(bool(row["converged"]) for row in rows),
        "n_failed": sum(not bool(row["converged"]) for row in rows),
        "convergence_ratio": sum(bool(row["converged"]) for row in rows) / len(rows),
        "n_labels_global": len(counts),
        "label_counts_global": dict(sorted(counts.items())),
        "n_slices": len(slice_counts),
        "slice_label_counts": slice_counts,
        "min_labels_within_slice": min(len(v) for v in slice_counts.values()),
        "section_slices": [
            {
                "name": section.name,
                "h": section.h,
                "b": section.b,
                "t1": section.t1,
                "t2": section.t2,
                "baseline_length": section.baseline_length,
            }
            for section in section_slices()
        ],
    }
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def write_figure(rows: list[dict[str, object]], history_rows: list[dict[str, object]], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = sorted({str(row["weak_state_label"]) for row in rows})
    palette = {
        "stiff_composite_like": "#3f6f9f",
        "slip_dominated": "#b0442e",
        "mixed_slip_stability": "#7a5195",
        "local_buckling_softening": "#d79a2b",
        "global_instability_sensitive": "#2f6f4e",
    }
    markers = {
        "small_H80_B80_T1-5_T2-7": "o",
        "medium_H100_B100_T1-6_T2-8": "s",
        "large_H140_B140_T1-8_T2-12": "^",
    }

    fig, axes = plt.subplots(2, 2, figsize=(11.5, 8.4), dpi=160)

    for slice_name in sorted({str(row["ieff_slice"]) for row in rows}):
        for label in labels:
            selected = [
                row
                for row in rows
                if row["ieff_slice"] == slice_name and row["weak_state_label"] == label
            ]
            if not selected:
                continue
            axes[0, 0].scatter(
                [float(row["global_instability_index"]) for row in selected],
                [float(row["slip_index"]) for row in selected],
                color=palette[label],
                marker=markers[slice_name],
                edgecolor="white",
                linewidth=0.45,
                s=42,
                alpha=0.9,
            )
    axes[0, 0].set_xlabel("Global-instability index")
    axes[0, 0].set_ylabel("Slip index")
    axes[0, 0].set_title("Full benchmark response-state map")

    slice_names = [section.name for section in section_slices()]
    label_counts = _slice_label_counts(rows)
    bottom = np.zeros(len(slice_names))
    x = np.arange(len(slice_names))
    for label in labels:
        values = np.asarray([label_counts[name].get(label, 0) for name in slice_names], dtype=float)
        axes[0, 1].bar(x, values, bottom=bottom, color=palette[label], label=label.replace("_", " "))
        bottom += values
    axes[0, 1].set_xticks(x, ["small", "medium", "large"])
    axes[0, 1].set_ylabel("Case count")
    axes[0, 1].set_title("Label coverage by fixed-I_eff slice")
    axes[0, 1].legend(frameon=False, fontsize=7)

    for slice_name in slice_names:
        selected = [row for row in rows if row["ieff_slice"] == slice_name]
        axes[1, 0].plot(
            [float(row["axial_ratio"]) for row in selected],
            [float(row["peak_base_reaction"]) for row in selected],
            linestyle="none",
            marker=markers[slice_name],
            markersize=5,
            label=slice_name.split("_")[0],
        )
    axes[1, 0].set_xlabel("Axial ratio")
    axes[1, 0].set_ylabel("Peak base reaction")
    axes[1, 0].set_title("Peak force by section slice")
    axes[1, 0].legend(frameon=False, fontsize=7)

    representative_ids = []
    for slice_name in slice_names:
        selected = [row for row in rows if row["ieff_slice"] == slice_name]
        representative_ids.append(min(selected, key=lambda row: float(row["final_min_q_b_over_q_b0"]))["case_id"])
    for case_id in representative_ids:
        summary_row = next(row for row in rows if row["case_id"] == case_id)
        rows_for_case = [row for row in history_rows if row["case_id"] == case_id]
        steps = sorted({int(row["step"]) for row in rows_for_case})
        q_b0 = float(summary_row["q_b0"])
        min_q = []
        for step in steps:
            q_values = [float(row["row_q_b"]) for row in rows_for_case if int(row["step"]) == step]
            min_q.append(min(q_values) / q_b0)
        axes[1, 1].plot(
            np.linspace(0.0, 1.0, len(steps)),
            min_q,
            lw=1.15,
            marker=markers[str(summary_row["ieff_slice"])],
            markevery=max(1, len(steps) // 8),
            label=f"{case_id} {str(summary_row['ieff_slice']).split('_')[0]}",
        )
    axes[1, 1].set_xlabel("Normalized cyclic step")
    axes[1, 1].set_ylabel("Minimum row q_b / q_b0")
    axes[1, 1].set_title("Most-relaxed q_b trajectory per slice")
    axes[1, 1].legend(frameon=False, fontsize=7)

    label_handles = [
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=palette[label], label=label.replace("_", " "), markersize=7)
        for label in labels
    ]
    marker_handles = [
        plt.Line2D([0], [0], marker=markers[name], color="k", linestyle="none", label=name.split("_")[0], markersize=6)
        for name in slice_names
    ]
    axes[0, 0].legend(handles=label_handles + marker_handles, frameon=False, fontsize=6, ncol=2)

    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)


def main() -> int:
    rows, history = run_benchmark(points_per_branch=30)
    write_csv(rows, BENCHMARK_CSV, BASE_COLUMNS)
    write_csv(history, HISTORY_CSV, HISTORY_COLUMNS)
    write_summary_json(rows, SUMMARY_JSON)
    write_figure(rows, history, FIGURE_PNG)

    n_converged = sum(bool(row["converged"]) for row in rows)
    slice_counts = _slice_label_counts(rows)
    print(f"w5_cases={len(rows)}")
    print(f"w5_converged={n_converged}")
    print(f"w5_failed={len(rows) - n_converged}")
    print(f"w5_convergence_ratio={n_converged / len(rows):.6g}")
    print(f"w5_slice_label_counts={slice_counts}")
    print(f"w5_outputs={BENCHMARK_CSV};{HISTORY_CSV};{SUMMARY_JSON};{FIGURE_PNG}")
    return 0 if n_converged / len(rows) >= 0.80 and max(len(v) for v in slice_counts.values()) >= 3 else 2


if __name__ == "__main__":
    raise SystemExit(main())
