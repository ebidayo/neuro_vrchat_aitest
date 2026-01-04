import pytest
from audio.idle_face_drift import compute_idle_face_drift

def test_idle_face_drift_determinism():
    # Fixed time, seed
    t1 = compute_idle_face_drift(now_ts=1000, seed=42, enabled=True)
    t2 = compute_idle_face_drift(now_ts=1000, seed=42, enabled=True)
    assert t1 == t2
    # Different time, different output
    t3 = compute_idle_face_drift(now_ts=1040, seed=42, enabled=True)
    assert t1 != t3

def test_idle_face_drift_disabled():
    t = compute_idle_face_drift(now_ts=1000, seed=42, enabled=False)
    assert t == {'valence': 0.0, 'interest': 0.0}
