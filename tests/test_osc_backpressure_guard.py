import pytest
from audio.osc_backpressure_guard import osc_backpressure_guard

def test_osc_backpressure_guard():
    # High latency reduces freq
    f = osc_backpressure_guard(150, 2.0)
    assert 0.5 <= f < 2.0
    # Low latency increases freq
    f2 = osc_backpressure_guard(40, 1.0)
    assert 1.0 < f2 <= 5.0
    # No change if normal
    f3 = osc_backpressure_guard(80, 1.5)
    assert 0.5 <= f3 <= 5.0
