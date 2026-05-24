from __future__ import annotations

import numpy as np

from solver.extended_member_model import row_shape_factors


def test_row_shape_profiles_are_distinct_and_positive() -> None:
    profiles = {
        name: row_shape_factors(3, name)
        for name in ("outer_amplified", "uniform", "outer_mild", "center_amplified")
    }
    for values in profiles.values():
        assert values.shape == (3,)
        assert np.all(values > 0)
    assert profiles["outer_amplified"][0] > profiles["outer_amplified"][1]
    assert profiles["center_amplified"][1] > profiles["center_amplified"][0]
    assert np.allclose(profiles["uniform"], np.ones(3))


def test_unknown_row_shape_profile_raises() -> None:
    try:
        row_shape_factors(3, "unknown")
    except ValueError as exc:
        assert "unknown row_shape_profile" in str(exc)
    else:
        raise AssertionError("unknown row-shape profile should raise ValueError")
