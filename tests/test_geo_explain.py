import math
import pytest

from core.geo_explain import estimate_coast_distance_km, pick_coast_distance_km


def test_estimate_coast_distance_returns_float():
    d = estimate_coast_distance_km(35.681236, 139.767125)  # Tokyo assumed
    assert isinstance(d, float)
    assert math.isfinite(d)
    assert d >= 0.0


def test_pick_coast_distance_prefers_override():
    user_loc = {"coast_distance_km": 12.5}
    d, src = pick_coast_distance_km(user_loc, 35.0, 139.0)
    assert d == pytest.approx(12.5)
    assert src == "override"


def test_pick_coast_distance_falls_back_to_estimate():
    user_loc = {"coast_distance_km": None, "lat": 35.681236, "lon": 139.767125}
    d, src = pick_coast_distance_km(user_loc, 35.681236, 139.767125)
    assert isinstance(d, float)
    assert math.isfinite(d)
    assert d >= 0.0
    assert src == "estimate"
