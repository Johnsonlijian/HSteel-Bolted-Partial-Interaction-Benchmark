"""Reduced-order member model for bolted built-up H-section screening.

Path-2 update (2026-05-22):

* The five screening calibration constants (axial slope, slenderness slope,
  local-buckling drift base, slip-shape factor, softening slope) are now
  exposed in `SCREENING_CALIBRATION_CONSTANTS` and consumed from there. They
  must be reported as a Methods table in the manuscript.
* `MemberParams` accepts optional preload-relaxation parameters
  (`relaxation_eta_dis`, `relaxation_q_residual`). When `relaxation_eta_dis`
  is positive, each bolt-row connector is coupled to a
  `BoltPreloadRelaxation` instance so that the bolt preload decays under
  accumulated frictional dissipation. When zero (default), behaviour is
  identical to the W1 baseline.
* `run_member_case` now also returns the per-row final preload `q_b_final`
  and the cumulative frictional dissipation, so calibration plots can be
  built from a single run.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .interface_law import (
    BoltPreloadRelaxation,
    PressureIndexedStickSlip,
    couple_relaxation_to_connector,
)
from .labels import classify_response


SCREENING_CALIBRATION_CONSTANTS: dict[str, float] = {
    # axial-load factor slope: 1 - AXIAL_FACTOR_SLOPE * axial_ratio
    "axial_factor_slope": 0.78,
    # slenderness factor slope: 1 / (1 + SLENDER_FACTOR_SLOPE *
    # max(0, slenderness - 40))
    "slender_factor_slope": 0.018,
    # local-buckling drift base: delta_lb = LOCAL_BUCKLING_BASE *
    # slender_factor * axial_factor * row_factor
    "local_buckling_base": 0.028,
    # bolt-row slip shape factor (default for MemberParams)
    "slip_shape_factor_default": 0.35,
    # local-softening slope: softening = 1 / (1 + SOFTENING_SLOPE *
    # local_index)
    "softening_slope": 1.35,
}
"""Five hand-picked screening factors that control phase-map shape.

These are reported as a single Methods table in the manuscript. They are
calibration constants, not derived mechanics; a full mechanical derivation
is left to future work.
"""


@dataclass(frozen=True)
class MemberParams:
    """Dimensionless parameters for the reduced-order member case.

    The five baseline calibration constants are pulled from
    `SCREENING_CALIBRATION_CONSTANTS`. They are kept centralized so that the
    manuscript Methods table is the single source of truth.

    Optional relaxation parameters
    ------------------------------
    relaxation_eta_dis:
        Decay rate per unit dissipated frictional work for the per-row
        `BoltPreloadRelaxation`. Zero disables relaxation (baseline).
    relaxation_q_residual:
        Lower-bound preload index after long-term relaxation. Ignored when
        `relaxation_eta_dis` is zero.
    """

    mu: float
    pressure_index: float
    bolt_rows: int
    axial_ratio: float
    slenderness: float
    interface_stiffness: float = 120.0
    limb_stiffness: float = 80.0
    slip_shape_factor: float = SCREENING_CALIBRATION_CONSTANTS[
        "slip_shape_factor_default"
    ]
    relaxation_eta_dis: float = 0.0
    relaxation_q_residual: float = 0.0


def cyclic_displacement_history(
    max_drift: float = 0.04, points_per_branch: int = 30
) -> np.ndarray:
    """Create a three-cycle symmetric displacement protocol."""

    amplitudes = [0.25 * max_drift, 0.55 * max_drift, max_drift]
    points: list[float] = [0.0]
    for amp in amplitudes:
        branch = [amp, -amp, amp, 0.0]
        current = points[-1]
        for target in branch:
            points.extend(np.linspace(current, target, points_per_branch + 1)[1:].tolist())
            current = target
    return np.asarray(points, dtype=float)


def _row_shapes(bolt_rows: int) -> np.ndarray:
    if bolt_rows < 1:
        raise ValueError("bolt_rows must be >= 1")
    x = np.linspace(-1.0, 1.0, bolt_rows)
    return 0.45 + 0.55 * np.abs(x)


def _global_stiffness(params: MemberParams) -> float:
    axial_slope = SCREENING_CALIBRATION_CONSTANTS["axial_factor_slope"]
    slender_slope = SCREENING_CALIBRATION_CONSTANTS["slender_factor_slope"]
    axial_factor = max(0.08, 1.0 - axial_slope * params.axial_ratio)
    slender_factor = 1.0 / (1.0 + slender_slope * max(0.0, params.slenderness - 40.0))
    return params.limb_stiffness * axial_factor * slender_factor


def _local_buckling_threshold(params: MemberParams) -> float:
    base = SCREENING_CALIBRATION_CONSTANTS["local_buckling_base"]
    slender_factor = max(0.35, 70.0 / max(params.slenderness, 1.0))
    axial_factor = max(0.25, 1.0 - 0.65 * params.axial_ratio)
    row_factor = 1.0 + 0.035 * max(0, params.bolt_rows - 3)
    return base * slender_factor * axial_factor * row_factor


def run_member_case(params: MemberParams, max_drift: float = 0.04) -> dict[str, object]:
    """Run one reduced-order cyclic case and return history and metrics.

    When `params.relaxation_eta_dis > 0`, each bolt-row connector is paired
    with a `BoltPreloadRelaxation` instance and the per-row preload index
    decays with accumulated frictional dissipation between steps.
    """

    history = cyclic_displacement_history(max_drift=max_drift)
    row_shapes = _row_shapes(params.bolt_rows)
    per_row_pressure = params.pressure_index / params.bolt_rows
    connectors = [
        PressureIndexedStickSlip(
            k_stick=params.interface_stiffness / params.bolt_rows,
            mu=params.mu,
            pressure_index=per_row_pressure,
        )
        for _ in range(params.bolt_rows)
    ]

    use_relaxation = params.relaxation_eta_dis > 0.0
    relaxations: list[BoltPreloadRelaxation] = []
    if use_relaxation:
        residual = min(params.relaxation_q_residual, per_row_pressure)
        relaxations = [
            BoltPreloadRelaxation(
                q_b0=per_row_pressure,
                q_b_residual=residual,
                eta_dis=params.relaxation_eta_dis,
            )
            for _ in range(params.bolt_rows)
        ]

    k_global = _global_stiffness(params)
    delta_lb = _local_buckling_threshold(params)
    softening_slope = SCREENING_CALIBRATION_CONSTANTS["softening_slope"]
    forces: list[float] = []
    slip_values: list[float] = []
    stick_fractions: list[float] = []
    local_indices: list[float] = []
    previous_row_slips = [0.0] * params.bolt_rows
    cumulative_dissipation = 0.0

    for delta in history:
        local_index = max(0.0, abs(delta) / delta_lb - 1.0)
        softening = 1.0 / (1.0 + softening_slope * local_index)
        global_force = k_global * delta * softening

        interface_force = 0.0
        sticking_count = 0
        for row_idx, (shape, connector) in enumerate(zip(row_shapes, connectors)):
            slip = (
                params.slip_shape_factor
                * shape
                * delta
                * (1.0 + 0.55 * params.axial_ratio)
            )
            force_i, sticking = connector.update(float(slip))

            if use_relaxation:
                slip_increment = float(slip - previous_row_slips[row_idx])
                _, force_i, sticking = couple_relaxation_to_connector(
                    connector,
                    relaxations[row_idx],
                    slip_increment,
                )

            previous_row_slips[row_idx] = float(slip)
            interface_force += 0.36 * force_i * shape
            sticking_count += int(sticking)
            slip_values.append(abs(slip))

        forces.append(global_force + interface_force)
        stick_fractions.append(sticking_count / params.bolt_rows)
        local_indices.append(local_index)

    if use_relaxation:
        cumulative_dissipation = sum(r.cumulative_dissipation for r in relaxations)

    force_arr = np.asarray(forces)
    drift_arr = history
    energy = float(np.trapezoid(force_arr, drift_arr))
    loop_energy = float(np.sum(np.abs(np.diff(drift_arr) * (force_arr[1:] + force_arr[:-1]) / 2.0)))
    max_force = float(np.max(np.abs(force_arr)))
    max_slip = float(np.max(slip_values) if slip_values else 0.0)
    mean_yield_slip = float(np.mean([c.yield_slip for c in connectors]))
    slip_index = max_slip / max(mean_yield_slip, 1e-9)
    local_buckling_index = float(np.max(local_indices))
    global_instability_index = float(params.axial_ratio * params.slenderness / 52.0)
    energy_index = loop_energy / max(max_force * max_drift, 1e-9)
    label = classify_response(
        slip_index=slip_index,
        local_buckling_index=local_buckling_index,
        global_instability_index=global_instability_index,
        energy_index=energy_index,
    )

    result: dict[str, object] = {
        "params": params,
        "drift": drift_arr,
        "force": force_arr,
        "peak_force": max_force,
        "signed_loop_work": energy,
        "loop_energy": loop_energy,
        "slip_index": slip_index,
        "max_slip": max_slip,
        "mean_yield_slip": mean_yield_slip,
        "mean_stick_fraction": float(np.mean(stick_fractions)),
        "local_buckling_index": local_buckling_index,
        "global_instability_index": global_instability_index,
        "energy_index": energy_index,
        "weak_state_label": label,
        "delta_lb": delta_lb,
        "k_global": k_global,
        "relaxation_active": use_relaxation,
        "cumulative_dissipation": float(cumulative_dissipation),
    }
    if use_relaxation:
        result["q_b_final_per_row"] = [float(r.q_b) for r in relaxations]
    return result
