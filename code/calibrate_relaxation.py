"""Fit bolt-preload relaxation parameters to DOI-anchored datasets.

The fitting trajectory uses solver.interface_law.BoltPreloadRelaxation.update
as the single source of truth for the discrete relaxation law.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import minimize

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from solver.interface_law import BoltPreloadRelaxation  # noqa: E402


REQUIRED_DATASET_COLUMNS = [
    "cycle_or_step",
    "preload_normalized",
    "dissipation_proxy",
    "source_doi",
    "source_table_or_figure",
    "extraction_note",
]

FIT_TABLE_COLUMNS = [
    "dataset_id",
    "source_doi",
    "n_points",
    "eta_dis",
    "eta_dis_ci_lo",
    "eta_dis_ci_hi",
    "q_b_residual",
    "q_b_residual_ci_lo",
    "q_b_residual_ci_hi",
    "rms_residual",
    "dissipation_map",
    "calibration_date",
]


@dataclass
class Dataset:
    dataset_id: str
    source_doi: str
    x: np.ndarray
    y: np.ndarray
    source_note: str
    extraction_notes: list[str]


@dataclass
class FitResult:
    eta_dis: float
    q_b_residual: float
    rms_residual: float
    predicted: np.ndarray
    eta_ci: tuple[float, float]
    qres_ci: tuple[float, float]


def load_dataset(path: Path) -> Dataset:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = [col for col in REQUIRED_DATASET_COLUMNS if col not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{path}: missing required columns: {', '.join(missing)}")
        rows = list(reader)
    if not rows:
        raise ValueError(f"{path}: empty dataset")

    doi_values = {row["source_doi"].strip() for row in rows}
    if "" in doi_values:
        raise ValueError(f"{path}: source_doi must be non-empty in every row")
    if len(doi_values) != 1:
        raise ValueError(f"{path}: expected exactly one source DOI, got {sorted(doi_values)}")

    x = np.array([float(row["dissipation_proxy"]) for row in rows], dtype=float)
    y = np.array([float(row["preload_normalized"]) for row in rows], dtype=float)
    if np.any((y < 0) | (y > 1)):
        raise ValueError(f"{path}: preload_normalized must lie in [0, 1]")
    if np.any(np.diff(x) < 0):
        order = np.argsort(x)
        x = x[order]
        y = y[order]

    return Dataset(
        dataset_id=path.stem,
        source_doi=doi_values.pop(),
        x=x,
        y=y,
        source_note=rows[0]["source_table_or_figure"],
        extraction_notes=[row["extraction_note"] for row in rows],
    )


def simulate_preload(
    dissipation_proxy: np.ndarray,
    eta_dis: float,
    q_b_residual: float,
    q_b0: float = 1.0,
) -> np.ndarray:
    relaxation = BoltPreloadRelaxation(
        q_b0=float(q_b0),
        q_b_residual=float(q_b_residual),
        eta_dis=float(eta_dis),
    )
    values = [float(q_b0)]
    previous = float(dissipation_proxy[0])
    for current in dissipation_proxy[1:]:
        increment = max(0.0, float(current) - previous)
        values.append(relaxation.update(increment))
        previous = float(current)
    return np.array(values, dtype=float)


def fit_points(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float, np.ndarray]:
    def loss(params: np.ndarray) -> float:
        eta_dis, q_b_residual = params
        pred = simulate_preload(x, eta_dis, q_b_residual)
        # Once the trajectory reaches q_b_residual, many larger eta values can
        # produce the same SSE. This tiny tie-breaker selects the smallest eta
        # compatible with the data without affecting plotted residuals.
        return float(np.sum((pred - y) ** 2) + 1.0e-9 * eta_dis)

    initial = np.array([0.01, max(0.0, min(0.95, float(np.min(y))))])
    result = minimize(
        loss,
        initial,
        method="L-BFGS-B",
        bounds=[(0.0, 1.0), (0.0, 1.0)],
    )
    if not result.success:
        raise RuntimeError(f"fit did not converge: {result.message}")
    eta_dis, q_b_residual = (float(result.x[0]), float(result.x[1]))
    best_sse = float(np.sum((simulate_preload(x, eta_dis, q_b_residual) - y) ** 2))
    eta_dis = smallest_equivalent_eta(x, y, q_b_residual, eta_dis, best_sse)
    predicted = simulate_preload(x, eta_dis, q_b_residual)
    rms = float(math.sqrt(np.mean((predicted - y) ** 2)))
    return eta_dis, q_b_residual, rms, predicted


def smallest_equivalent_eta(
    x: np.ndarray,
    y: np.ndarray,
    q_b_residual: float,
    eta_hi: float,
    best_sse: float,
) -> float:
    """Choose the smallest eta with indistinguishable SSE for plateau fits."""

    tolerance = max(1.0e-10, best_sse * 1.0e-8)

    def sse(eta: float) -> float:
        return float(np.sum((simulate_preload(x, eta, q_b_residual) - y) ** 2))

    if eta_hi <= 0 or sse(0.0) <= best_sse + tolerance:
        return 0.0

    grid = np.linspace(0.0, eta_hi, 1001)
    first = eta_hi
    for value in grid:
        if sse(float(value)) <= best_sse + tolerance:
            first = float(value)
            break

    lo = max(0.0, first - eta_hi / 1000.0)
    hi = first
    for _ in range(50):
        mid = (lo + hi) / 2
        if sse(mid) <= best_sse + tolerance:
            hi = mid
        else:
            lo = mid
    return hi


def bootstrap_ci(
    x: np.ndarray,
    y: np.ndarray,
    predicted: np.ndarray,
    bootstrap: int,
    seed: int,
) -> tuple[tuple[float, float], tuple[float, float]]:
    if bootstrap <= 0:
        return (math.nan, math.nan), (math.nan, math.nan)
    rng = np.random.default_rng(seed)
    residuals = y - predicted
    eta_values: list[float] = []
    qres_values: list[float] = []
    for _ in range(bootstrap):
        boot_y = np.clip(predicted + rng.choice(residuals, size=len(residuals), replace=True), 0, 1)
        try:
            eta_dis, q_b_residual, _, _ = fit_points(x, boot_y)
        except RuntimeError:
            continue
        eta_values.append(eta_dis)
        qres_values.append(q_b_residual)
    if not eta_values:
        return (math.nan, math.nan), (math.nan, math.nan)
    return (
        (float(np.percentile(eta_values, 2.5)), float(np.percentile(eta_values, 97.5))),
        (float(np.percentile(qres_values, 2.5)), float(np.percentile(qres_values, 97.5))),
    )


def fit_dataset(dataset: Dataset, bootstrap: int, seed: int) -> FitResult:
    eta_dis, q_b_residual, rms, predicted = fit_points(dataset.x, dataset.y)
    eta_ci, qres_ci = bootstrap_ci(dataset.x, dataset.y, predicted, bootstrap, seed)
    return FitResult(
        eta_dis=eta_dis,
        q_b_residual=q_b_residual,
        rms_residual=rms,
        predicted=predicted,
        eta_ci=eta_ci,
        qres_ci=qres_ci,
    )


def write_fit_table(datasets: list[Dataset], fits: dict[str, FitResult], out_table: Path) -> None:
    out_table.parent.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    rows: list[dict[str, str]] = []
    for dataset in datasets:
        fit = fits[dataset.dataset_id]
        rows.append(
            {
                "dataset_id": dataset.dataset_id,
                "source_doi": dataset.source_doi,
                "n_points": str(len(dataset.y)),
                "eta_dis": f"{fit.eta_dis:.8g}",
                "eta_dis_ci_lo": f"{fit.eta_ci[0]:.8g}",
                "eta_dis_ci_hi": f"{fit.eta_ci[1]:.8g}",
                "q_b_residual": f"{fit.q_b_residual:.8g}",
                "q_b_residual_ci_lo": f"{fit.qres_ci[0]:.8g}",
                "q_b_residual_ci_hi": f"{fit.qres_ci[1]:.8g}",
                "rms_residual": f"{fit.rms_residual:.8g}",
                "dissipation_map": "cycle index proxy; dW_f=1 per reported thermal cycle",
                "calibration_date": today,
            }
        )

    eta_points = [fits[d.dataset_id].eta_dis for d in datasets]
    qres_points = [fits[d.dataset_id].q_b_residual for d in datasets]
    eta_los = [fits[d.dataset_id].eta_ci[0] for d in datasets]
    eta_his = [fits[d.dataset_id].eta_ci[1] for d in datasets]
    qres_los = [fits[d.dataset_id].qres_ci[0] for d in datasets]
    qres_his = [fits[d.dataset_id].qres_ci[1] for d in datasets]
    rows.append(
        {
            "dataset_id": "pooled",
            "source_doi": ";".join(dataset.source_doi for dataset in datasets),
            "n_points": str(sum(len(dataset.y) for dataset in datasets)),
            "eta_dis": f"{float(np.median(eta_points)):.8g}",
            "eta_dis_ci_lo": f"{float(np.nanmin(eta_los)):.8g}",
            "eta_dis_ci_hi": f"{float(np.nanmax(eta_his)):.8g}",
            "q_b_residual": f"{float(np.median(qres_points)):.8g}",
            "q_b_residual_ci_lo": f"{float(np.nanmin(qres_los)):.8g}",
            "q_b_residual_ci_hi": f"{float(np.nanmax(qres_his)):.8g}",
            "rms_residual": f"{float(np.mean([fits[d.dataset_id].rms_residual for d in datasets])):.8g}",
            "dissipation_map": "equal-weight median of per-dataset cycle-proxy fits",
            "calibration_date": today,
        }
    )

    with out_table.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIT_TABLE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def sensitivity_lines(dataset: Dataset) -> list[str]:
    lines = []
    for scale in (0.5, 1.0, 2.0):
        x_scaled = dataset.x * scale
        eta, qres, rms, _ = fit_points(x_scaled, dataset.y)
        lines.append(
            f"- scale={scale:g}: eta_dis={eta:.6g}, q_b_residual={qres:.6g}, RMS={rms:.6g}"
        )
    return lines


def write_diagnostics(datasets: list[Dataset], fits: dict[str, FitResult], out_diag: Path) -> None:
    out_diag.parent.mkdir(parents=True, exist_ok=True)
    parts = [
        "# Relaxation Fit Diagnostics",
        "",
        f"Calibration date: {date.today().isoformat()}",
        "",
        "The W2 data report preload vs. thermal cycle count, not measured frictional work.",
        "Following the brief, `dissipation_proxy` maps each reported cycle to `dW_f=1`.",
        "Sensitivity below rescales that proxy; eta changes with the scale, while residual preload is more stable.",
        "When the trajectory reaches the fitted residual plateau, eta is only lower-bound identifiable; the fitter uses a tiny eta tie-breaker to choose the smallest eta with the same SSE.",
        "",
    ]
    for dataset in datasets:
        fit = fits[dataset.dataset_id]
        parts.extend(
            [
                f"## {dataset.dataset_id}",
                "",
                f"- DOI: `{dataset.source_doi}`",
                f"- Points: {len(dataset.y)}",
                f"- Source: {dataset.source_note}",
                f"- eta_dis: {fit.eta_dis:.6g} "
                f"(95% residual-bootstrap CI {fit.eta_ci[0]:.6g} to {fit.eta_ci[1]:.6g})",
                f"- q_b_residual: {fit.q_b_residual:.6g} "
                f"(95% residual-bootstrap CI {fit.qres_ci[0]:.6g} to {fit.qres_ci[1]:.6g})",
                f"- RMS residual: {fit.rms_residual:.6g}",
                "- Dissipation-proxy sensitivity:",
                *sensitivity_lines(dataset),
                "",
                "Extraction notes:",
            ]
        )
        for note in dataset.extraction_notes:
            parts.append(f"- {note}")
        parts.append("")
    out_diag.write_text("\n".join(parts), encoding="utf-8")


def write_figure(datasets: list[Dataset], fits: dict[str, FitResult], out_fig: Path) -> None:
    out_fig.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, len(datasets), figsize=(6.4 * len(datasets), 4.4), squeeze=False)
    for ax, dataset in zip(axes[0], datasets):
        fit = fits[dataset.dataset_id]
        ax.plot(dataset.x, dataset.y, "o", label="reported data")
        ax.plot(dataset.x, fit.predicted, "-", label="fitted update law")
        ax.set_title(dataset.dataset_id)
        ax.set_xlabel("dissipation proxy / cycle")
        ax.set_ylabel("normalized preload")
        ax.set_ylim(-0.02, 1.05)
        ax.grid(True, alpha=0.25)
        ax.legend()
    fig.tight_layout()
    fig.savefig(out_fig, dpi=200)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--datasets", nargs="+", type=Path, required=True)
    parser.add_argument("--out-table", type=Path, required=True)
    parser.add_argument("--out-diag", type=Path, required=True)
    parser.add_argument("--out-fig", type=Path, required=True)
    parser.add_argument("--bootstrap", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20260522)
    args = parser.parse_args()

    datasets = [load_dataset(path) for path in args.datasets]
    fits = {
        dataset.dataset_id: fit_dataset(dataset, args.bootstrap, args.seed + i)
        for i, dataset in enumerate(datasets)
    }
    write_fit_table(datasets, fits, args.out_table)
    write_diagnostics(datasets, fits, args.out_diag)
    write_figure(datasets, fits, args.out_fig)

    print(f"wrote={args.out_table}")
    print(f"wrote={args.out_diag}")
    print(f"wrote={args.out_fig}")
    for dataset in datasets:
        fit = fits[dataset.dataset_id]
        print(
            f"{dataset.dataset_id}: eta_dis={fit.eta_dis:.6g}, "
            f"q_b_residual={fit.q_b_residual:.6g}, rms={fit.rms_residual:.6g}"
        )


if __name__ == "__main__":
    main()
