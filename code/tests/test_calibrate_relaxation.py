"""Synthetic recovery test for the R06 W2 relaxation calibrator."""

from __future__ import annotations

import sys
import importlib.util
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

CALIBRATOR_PATH = PROJECT_ROOT / "code" / "calibrate_relaxation.py"
spec = importlib.util.spec_from_file_location("calibrate_relaxation", CALIBRATOR_PATH)
assert spec is not None and spec.loader is not None
calibrator = importlib.util.module_from_spec(spec)
sys.modules["calibrate_relaxation"] = calibrator
spec.loader.exec_module(calibrator)
fit_points = calibrator.fit_points
simulate_preload = calibrator.simulate_preload


def main() -> None:
    rng = np.random.default_rng(20260522)
    x = np.arange(50, dtype=float)
    eta_true = 0.02
    qres_true = 0.4
    clean = simulate_preload(x, eta_true, qres_true)

    # Five-percent Gaussian measurement noise, scaled by the distance to the
    # residual plateau so the known plateau remains identifiable.
    noise_scale = 0.05 * np.maximum(clean - qres_true, 0.02)
    noisy = np.clip(clean + rng.normal(0.0, noise_scale), 0.0, 1.0)
    noisy[0] = 1.0

    eta_hat, qres_hat, rms, _ = fit_points(x, noisy)
    eta_rel_err = abs(eta_hat - eta_true) / eta_true
    qres_rel_err = abs(qres_hat - qres_true) / qres_true

    print(f"eta_true={eta_true:.6g} eta_hat={eta_hat:.6g} rel_err={eta_rel_err:.4f}")
    print(f"qres_true={qres_true:.6g} qres_hat={qres_hat:.6g} rel_err={qres_rel_err:.4f}")
    print(f"rms={rms:.6g}")

    assert eta_rel_err <= 0.05, "eta_dis recovery exceeds 5% relative error"
    assert qres_rel_err <= 0.05, "q_b_residual recovery exceeds 5% relative error"


if __name__ == "__main__":
    main()
