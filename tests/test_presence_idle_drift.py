import math
from osc.presence_idle_drift import IdleFaceDrift, clamp

class MockOSC:
    def __init__(self):
        self.calls = []
    def send(self, param, value):
        self.calls.append((param, value))

class MockTimeProvider:
    def __init__(self, times):
        self.times = times
        self.idx = 0
    def now(self):
        t = self.times[self.idx]
        self.idx += 1
        return t

def test_drift_determinism():
    osc = MockOSC()
    times = [1000, 1005, 1010]
    config = {
        'enable_idle_face_drift': True,
        'idle_face_drift_amp': 0.04,
        'idle_face_drift_period_sec': 50.0,
        'idle_face_drift_tick_hz': 0.2,
        'presence_seed': 42
    }
    drift = IdleFaceDrift(osc, MockTimeProvider(times), config, clamp, lambda: "IDLE", lambda: False)
    for _ in times:
        drift.tick()
    # Should emit 3 calls per param
    vals = [v for p, v in osc.calls if p == '/avatar/parameters/face_valence']
    assert len(vals) == 3
    # Deterministic: same config/times yields same output
    osc2 = MockOSC()
    drift2 = IdleFaceDrift(osc2, MockTimeProvider(times), config, clamp, lambda: "IDLE", lambda: False)
    for _ in times:
        drift2.tick()
    vals2 = [v for p, v in osc2.calls if p == '/avatar/parameters/face_valence']
    assert vals == vals2

def test_drift_gating():
    osc = MockOSC()
    config = {'enable_idle_face_drift': True, 'idle_face_drift_amp': 0.04, 'idle_face_drift_period_sec': 50.0, 'idle_face_drift_tick_hz': 0.2, 'presence_seed': 42}
    drift = IdleFaceDrift(osc, MockTimeProvider([1000]), config, clamp, lambda: "ALERT", lambda: False)
    drift.tick()
    assert not osc.calls
    drift2 = IdleFaceDrift(osc, MockTimeProvider([1000]), config, clamp, lambda: "IDLE", lambda: True)
    drift2.tick()
    assert not osc.calls
    config_off = dict(config)
    config_off['enable_idle_face_drift'] = False
    drift3 = IdleFaceDrift(osc, MockTimeProvider([1000]), config_off, clamp, lambda: "IDLE", lambda: False)
    drift3.tick()
    assert not osc.calls

def test_drift_clamp():
    osc = MockOSC()
    config = {'enable_idle_face_drift': True, 'idle_face_drift_amp': 0.08, 'idle_face_drift_period_sec': 30.0, 'idle_face_drift_tick_hz': 0.2, 'presence_seed': 42}
    drift = IdleFaceDrift(osc, MockTimeProvider([1000]), config, clamp, lambda: "IDLE", lambda: False)
    drift.tick()
    vals = [v for p, v in osc.calls if p == '/avatar/parameters/face_valence']
    assert all(abs(v) <= 1.0 for v in vals)
import pytest
from osc.presence_idle_drift import compute_idle_drift
from core.determinism import TimeProvider

def test_idle_drift_determinism():
    # Fixed time, seed, amp, period
    t1 = compute_idle_drift(1000, 1337, 0.04, 50.0)
    t2 = compute_idle_drift(1000, 1337, 0.04, 50.0)
    assert t1 == t2
    # Different time, different output
    t3 = compute_idle_drift(1050, 1337, 0.04, 50.0)
    assert t1 != t3
    # Clamp
    t4 = compute_idle_drift(1000, 1337, 0.08, 30.0)
    assert abs(t4['valence']) <= 0.05
    assert abs(t4['interest']) <= 0.05 * 0.8
