import pytest
from emergency import EmergencyController, EmergencyDecision

class FakeClock:
    def __init__(self, t=0.0):
        self.t = t
    def now(self):
        return self.t
    def advance(self, dt):
        self.t += dt

class FakeBeepPlayer:
    def __init__(self):
        self.calls = []
    def play(self, path):
        self.calls.append(path)
        return True

def make_cfg(**kw):
    cfg = {
        "enabled": True,
        "cooldown_sec": 10.0,
        "beep_wav_path": "assets/beep.wav",
        "force_language_ja": True,
        "active_hold_sec": 10.0,
    }
    cfg.update(kw)
    return cfg

def test_disabled_never_alerts():
    clock = FakeClock()
    beep = FakeBeepPlayer()
    cfg = make_cfg(enabled=False)
    ctrl = EmergencyController(cfg, clock, logger=FakeLogger(), beep_player=beep)
    dec = ctrl.maybe_trigger("地震です", reason="test")
    assert not dec.should_alert
    assert len(beep.calls) == 0

def test_first_trigger_alerts():
    clock = FakeClock()
    beep = FakeBeepPlayer()
    ctrl = EmergencyController(make_cfg(), clock, logger=FakeLogger(), beep_player=beep)
    dec = ctrl.maybe_trigger("地震です", reason="test")
    assert dec.should_alert
    assert len(beep.calls) == 1

def test_same_message_within_cooldown():
    clock = FakeClock()
    beep = FakeBeepPlayer()
    ctrl = EmergencyController(make_cfg(), clock, logger=FakeLogger(), beep_player=beep)
    dec1 = ctrl.maybe_trigger("地震です", reason="test")
    assert dec1.should_alert
    clock.advance(2)
    dec2 = ctrl.maybe_trigger("地震です", reason="test")
    assert not dec2.should_alert
    assert dec2.suppressed_by_cooldown
    assert len(beep.calls) == 1

def test_different_message_within_cooldown():
    clock = FakeClock()
    beep = FakeBeepPlayer()
    ctrl = EmergencyController(make_cfg(), clock, logger=FakeLogger(), beep_player=beep)
    dec1 = ctrl.maybe_trigger("地震です", reason="test")
    assert dec1.should_alert
    clock.advance(2)
    dec2 = ctrl.maybe_trigger("津波です", reason="test")
    assert dec2.should_alert
    assert len(beep.calls) == 2

def test_after_cooldown():
    clock = FakeClock()
    beep = FakeBeepPlayer()
    ctrl = EmergencyController(make_cfg(), clock, logger=FakeLogger(), beep_player=beep)
    dec1 = ctrl.maybe_trigger("地震です", reason="test")
    assert dec1.should_alert
    clock.advance(12)
    dec2 = ctrl.maybe_trigger("地震です", reason="test")
    assert dec2.should_alert
    assert len(beep.calls) == 2

def test_missing_beep_path():
    clock = FakeClock()
    beep = FakeBeepPlayer()
    cfg = make_cfg(beep_wav_path="")
    ctrl = EmergencyController(cfg, clock, logger=FakeLogger(), beep_player=beep)
    dec = ctrl.maybe_trigger("地震です", reason="test")
    assert dec.should_alert
    assert len(beep.calls) == 0

class FakeLogger:
    def info(self, *a, **k):
        pass
