import pytest
from osc.presence_blink import PresenceBlink
from core.determinism import TimeProvider

class DummyOSC:
    def __init__(self):
        self.calls = []
    def send_param(self, name, value):
        self.calls.append((name, value))

def test_blink_determinism():
    osc = DummyOSC()
    cfg = {'enable_blink_hint': True, 'blink_min_sec': 3.0, 'blink_max_sec': 8.0, 'blink_pulse_ms': 120, 'presence_seed': 42}
    tp = TimeProvider([1000, 1003.5, 1003.62, 1008])
    blink = PresenceBlink(osc, cfg, tp)
    # First tick: should blink
    blink.tick('IDLE', False)
    assert osc.calls and osc.calls[0][1] == 1
    # Pulse end
    blink.tick('IDLE', False)
    assert osc.calls[-1][1] == 0
    # Next tick: not due yet
    blink.tick('IDLE', False)
    assert osc.calls[-1][1] == 0
    # Next blink due
    blink.tick('IDLE', False)
    assert osc.calls[-1][1] == 1

def test_blink_suppressed_when_speaking():
    osc = DummyOSC()
    cfg = {'enable_blink_hint': True, 'blink_min_sec': 3.0, 'blink_max_sec': 8.0, 'blink_pulse_ms': 120, 'presence_seed': 42}
    tp = TimeProvider([1000])
    blink = PresenceBlink(osc, cfg, tp)
    blink.tick('IDLE', True)
    assert not osc.calls
