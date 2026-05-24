"""Interface laws for pressure-indexed frictional partial interaction.

Path-2 increment (2026-05-22): the previous `PressureIndexedStickSlip` modeled
a static-preload Coulomb friction limit. This file now adds
`BoltPreloadRelaxation`, a slow internal variable that lets the effective
preload index decay under accumulated frictional dissipation. The two classes
are intentionally separate so that a relaxation-free baseline remains
available for comparison.

The relaxation law links bolted-joint loosening behaviour (typically
documented in mechanical-engineering / tribology literature) with structural
partial-interaction theory (typically documented in civil / steel-structure
literature), which are usually treated separately. It is the mechanics
increment that lifts the screening framework above textbook Coulomb friction.

Neither class is a replacement for continuum contact FE. Both are
reproducible mechanics kernels for screening response regimes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StickSlipState:
    """Internal state for a one-dimensional frictional connector."""

    plastic_slip: float = 0.0
    force: float = 0.0
    sticking: bool = True


@dataclass
class PressureIndexedStickSlip:
    """Perfectly plastic stick-slip law with pressure-indexed friction limit.

    The friction limit is `mu * pressure_index`. `pressure_index` is an
    equivalent normal pressure / preload index `q_b`. It can be held constant
    (baseline use) or driven by a `BoltPreloadRelaxation` instance via
    `set_pressure()` between increments.

    Parameters
    ----------
    k_stick:
        Initial elastic shear stiffness of the connector.
    mu:
        Friction coefficient or equivalent friction index.
    pressure_index:
        Equivalent normal pressure/preload index q_b. This is not a direct
        bolt pretension unless a high-fidelity model or experiment confirms it.
    """

    k_stick: float
    mu: float
    pressure_index: float
    state: StickSlipState | None = None

    def __post_init__(self) -> None:
        if self.k_stick <= 0:
            raise ValueError("k_stick must be positive")
        if self.mu < 0:
            raise ValueError("mu must be non-negative")
        if self.pressure_index < 0:
            raise ValueError("pressure_index must be non-negative")
        if self.state is None:
            self.state = StickSlipState()

    @property
    def yield_force(self) -> float:
        return self.mu * self.pressure_index

    @property
    def yield_slip(self) -> float:
        if self.k_stick == 0:
            return float("inf")
        return self.yield_force / self.k_stick

    def set_pressure(self, new_pressure_index: float) -> None:
        """Update the pressure index between increments.

        Use this when the connector is coupled to a `BoltPreloadRelaxation`
        instance. The plastic slip state is preserved across the update.
        """

        if new_pressure_index < 0:
            raise ValueError("pressure_index must be non-negative")
        self.pressure_index = new_pressure_index

    def reset(self) -> None:
        self.state = StickSlipState()

    def update(self, slip: float) -> tuple[float, bool]:
        """Update connector state for an imposed relative slip."""

        assert self.state is not None
        trial_force = self.k_stick * (slip - self.state.plastic_slip)
        limit = self.yield_force

        if limit <= 0:
            self.state.force = 0.0
            self.state.plastic_slip = slip
            self.state.sticking = False
            return self.state.force, self.state.sticking

        if abs(trial_force) <= limit:
            self.state.force = trial_force
            self.state.sticking = True
            return self.state.force, self.state.sticking

        sign = 1.0 if trial_force >= 0 else -1.0
        self.state.force = sign * limit
        self.state.plastic_slip = slip - self.state.force / self.k_stick
        self.state.sticking = False
        return self.state.force, self.state.sticking

    def increment_dissipation(self, slip_increment: float) -> float:
        """Return the frictional dissipation increment for the last update.

        The caller passes the increment of the imposed slip variable. When
        the connector is in the sliding regime, dissipation is approximated
        as `|force * slip_increment|`. When sticking, dissipation is zero.
        This is the quantity that drives `BoltPreloadRelaxation.update()`.
        """

        assert self.state is not None
        if self.state.sticking:
            return 0.0
        return abs(self.state.force * slip_increment)


@dataclass
class BoltPreloadRelaxation:
    """Slow preload-relaxation internal variable for cyclic loading.

    Path-2 novelty (2026-05-22). The preload index `q_b` is treated as a slow
    internal variable that decays with accumulated frictional dissipation in
    the bolt-row connector. The decay reproduces bolt-loosening behaviour
    documented in tribology / mechanical-engineering literature; combined with
    `PressureIndexedStickSlip`, it embeds bolt loosening directly into a
    structural partial-interaction model.

    Discrete update per loading increment:

        q_b <- q_b - eta_dis * |dW_friction|
        q_b <- max(q_b, q_b_residual)

    Parameters
    ----------
    q_b0:
        Initial preload index. Non-negative.
    q_b_residual:
        Lower-bound preload index after long-term relaxation. Must satisfy
        0 <= q_b_residual <= q_b0.
    eta_dis:
        Decay rate per unit dissipated frictional work. Non-negative. Must
        be calibrated against published bolt-loosening data; the W2 task
        packet documents the calibration plan.
    """

    q_b0: float
    q_b_residual: float = 0.0
    eta_dis: float = 0.0
    q_b: float | None = None
    cumulative_dissipation: float = 0.0

    def __post_init__(self) -> None:
        if self.q_b0 < 0:
            raise ValueError("q_b0 must be non-negative")
        if self.q_b_residual < 0 or self.q_b_residual > self.q_b0:
            raise ValueError("q_b_residual must satisfy 0 <= q_b_residual <= q_b0")
        if self.eta_dis < 0:
            raise ValueError("eta_dis must be non-negative")
        if self.q_b is None:
            self.q_b = self.q_b0

    def update(self, dissipation_increment: float) -> float:
        """Decrement preload by the dissipation increment and return q_b.

        `dissipation_increment` is non-negative dissipated frictional work in
        the bolt-row connector for the most recent step. A zero increment
        leaves the preload unchanged.
        """

        assert self.q_b is not None
        if dissipation_increment < 0:
            raise ValueError("dissipation_increment must be non-negative")
        self.cumulative_dissipation += dissipation_increment
        self.q_b -= self.eta_dis * dissipation_increment
        if self.q_b < self.q_b_residual:
            self.q_b = self.q_b_residual
        return self.q_b

    def reset(self) -> None:
        self.q_b = self.q_b0
        self.cumulative_dissipation = 0.0


def couple_relaxation_to_connector(
    connector: PressureIndexedStickSlip,
    relaxation: BoltPreloadRelaxation,
    slip_increment: float,
) -> tuple[float, float, bool]:
    """Advance a relaxation-coupled connector by one slip increment.

    1. Compute frictional dissipation from the last connector update.
    2. Update the relaxation state.
    3. Push the new preload index back into the connector for the next call.

    Returns ``(q_b_new, connector_force, sticking)``.
    """

    dissipation = connector.increment_dissipation(slip_increment)
    q_b_new = relaxation.update(dissipation)
    connector.set_pressure(q_b_new)
    assert connector.state is not None
    return q_b_new, connector.state.force, connector.state.sticking
