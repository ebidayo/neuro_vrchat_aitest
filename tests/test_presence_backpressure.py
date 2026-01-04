import pytest
from osc.presence_backpressure import PresenceBackpressure

def test_backpressure_downgrade_recover():
    cfg = {'osc_latency_downgrade_ms': 35, 'osc_latency_recover_ms': 20, 'osc_face_update_hz_danger': 0.05, 'idle_face_drift_tick_hz': 0.2}
    bp = PresenceBackpressure(cfg)
    # Add high latency samples
    for _ in range(10):
        bp.add_latency(50)
    hz = bp.tick(100)
    assert hz == cfg['osc_face_update_hz_danger']
    # Add low latency samples
    for _ in range(10):
        bp.add_latency(10)
    hz2 = bp.tick(140)
    assert hz2 == cfg['idle_face_drift_tick_hz']
