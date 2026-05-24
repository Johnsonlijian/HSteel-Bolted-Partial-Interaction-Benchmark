"""Response labels for reduced-order phase maps.

The thresholds below are **screening calibration constants**. They control
how the reduced-order solver assigns weak labels to cases. They are exposed
here (rather than hidden inside larger functions) so that the manuscript can
report them in a single Methods table and so that reviewers can audit and
replace them after calibration.

The five primary calibration constants for the reduced-order solver
(combining this file and `reduced_member_model.py`) are listed in
`solver/README.md` "Calibration Constants" section.
"""

from __future__ import annotations


# --- Screening calibration constants (exposed for the Methods table) ---

GLOBAL_INSTABILITY_THRESHOLD: float = 0.78
"""Above this index value, the case is labeled global-instability-sensitive."""

LOCAL_BUCKLING_THRESHOLD: float = 0.35
"""Above this index value, the case is labeled local-buckling-softening."""

SLIP_DOMINANT_INDEX: float = 1.0
"""Slip-index lower bound for a slip-dominant label, together with the
energy-index requirement below."""

SLIP_DOMINANT_ENERGY_FLOOR: float = 0.02
"""Energy-index floor that must accompany SLIP_DOMINANT_INDEX for a label
of slip-dominated."""

MIXED_SLIP_INDEX_FLOOR: float = 0.65
"""Below SLIP_DOMINANT_INDEX but above this floor, the case is labeled
mixed slip-stability."""


def classify_response(
    *,
    slip_index: float,
    local_buckling_index: float,
    global_instability_index: float,
    energy_index: float,
) -> str:
    """Return a conservative weak response label.

    The thresholds (`GLOBAL_INSTABILITY_THRESHOLD`,
    `LOCAL_BUCKLING_THRESHOLD`, `SLIP_DOMINANT_INDEX`,
    `SLIP_DOMINANT_ENERGY_FLOOR`, `MIXED_SLIP_INDEX_FLOOR`) are screening
    constants, not validated thresholds. They must be reported in the
    manuscript Methods table alongside any classification claim.
    """

    if global_instability_index >= GLOBAL_INSTABILITY_THRESHOLD:
        return "global_instability_sensitive"
    if local_buckling_index >= LOCAL_BUCKLING_THRESHOLD:
        return "local_buckling_softening"
    if slip_index >= SLIP_DOMINANT_INDEX and energy_index >= SLIP_DOMINANT_ENERGY_FLOOR:
        return "slip_dominated"
    if slip_index >= MIXED_SLIP_INDEX_FLOOR:
        return "mixed_slip_stability"
    return "stiff_composite_like"


LABEL_TO_CODE = {
    "stiff_composite_like": 0,
    "slip_dominated": 1,
    "local_buckling_softening": 2,
    "global_instability_sensitive": 3,
    "mixed_slip_stability": 4,
}
