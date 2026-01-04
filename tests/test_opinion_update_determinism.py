import pytest
from opinion import OpinionState, update_opinion

def test_opinion_update_determinism():
    state = OpinionState()
    signals = {"concise_vs_detailed": 0.8, "playful_vs_serious": -0.5}
    now = 1000.0
    s1 = update_opinion(state, signals, now, alpha=0.01)
    s2 = update_opinion(state, signals, now, alpha=0.01)
    assert s1 == s2
    # Changing signals changes output
    s3 = update_opinion(state, {"concise_vs_detailed": -0.8}, now, alpha=0.01)
    assert s3 != s1
    # Clamp
    s4 = update_opinion(state, {"concise_vs_detailed": 10.0}, now, alpha=0.01)
    assert -1.0 <= s4.concise_vs_detailed <= 1.0
