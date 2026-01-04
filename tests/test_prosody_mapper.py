import pytest
from audio.prosody_mapper import map_prosody

def test_map_prosody_defaults():
    # Neutral
    p = map_prosody(0.0, 0.0, 0.0)
    assert 0.99 < p['pitch'] < 1.01
    assert 0.99 < p['speed'] < 1.01
    assert 0.79 < p['energy'] < 0.81
    # Positive valence/interest/arousal
    p = map_prosody(1.0, 1.0, 1.0)
    assert 1.1 < p['pitch'] <= 1.3
    assert 1.1 < p['speed'] <= 1.5
    assert 1.0 < p['energy'] <= 1.5
    # Negative valence
    p = map_prosody(-1.0, 0.0, 0.0)
    assert 0.7 <= p['pitch'] < 1.0
    # Clamp test
    p = map_prosody(10, 10, 10)
    assert 0.7 <= p['pitch'] <= 1.3
    assert 0.7 <= p['speed'] <= 1.5
    assert 0.5 <= p['energy'] <= 1.5

def test_map_prosody_config():
    cfg = {'audio': {'prosody': {'pitch_gain': 0.2, 'speed_gain': 0.3, 'energy_gain': 0.4}}}
    p = map_prosody(1.0, 1.0, 1.0, cfg)
    assert 1.1 < p['pitch'] <= 1.3
    assert 1.2 < p['speed'] <= 1.5
    assert 1.1 < p['energy'] <= 1.5
