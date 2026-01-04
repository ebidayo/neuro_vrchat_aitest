import pytest
import time
from audio.thought_leakage import ThoughtLeakage

def test_thought_leakage_cooldown():
    tl = ThoughtLeakage()
    tl.enabled = True
    now = 1000.0
    # First emit
    token = tl.maybe_emit(0.6, 0.6, "IDLE", now_ts=now)
    assert token in ["...", "えっと", "んー"]
    # Cooldown blocks next emit
    token2 = tl.maybe_emit(0.6, 0.6, "IDLE", now_ts=now+10)
    assert token2 is None
    # After cooldown, emits again
    token3 = tl.maybe_emit(0.6, 0.6, "IDLE", now_ts=now+100)
    assert token3 in ["...", "えっと", "んー"]
    # Not in IDLE, never emits
    token4 = tl.maybe_emit(0.6, 0.6, "ALERT", now_ts=now+200)
    assert token4 is None
