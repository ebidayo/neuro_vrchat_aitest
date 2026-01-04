import pytest
from audio.breath import maybe_play_breath

def test_breath_trigger_gating():
    # Should not play if disabled
    assert maybe_play_breath(0.5, 0.5, "IDLE", after_wav=True, enabled=False) is None
    # Should not play if after_wav is False
    assert maybe_play_breath(0.5, 0.5, "IDLE", after_wav=False, enabled=True) is None
    # Should not play in ALERT/SEARCH/NAME_LEARNING
    for st in ("ALERT", "SEARCH", "NAME_LEARNING"):
        assert maybe_play_breath(0.5, 0.5, st, after_wav=True, enabled=True) is None
    # Should not play if arousal/confidence too low
    assert maybe_play_breath(0.2, 0.5, "IDLE", after_wav=True, enabled=True) is None
    assert maybe_play_breath(0.5, 0.2, "IDLE", after_wav=True, enabled=True) is None
