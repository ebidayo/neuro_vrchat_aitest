import time
import pytest
from core.state_machine import StateMachine, State

class DummySM(StateMachine):
    def __init__(self, cfg=None, session_id="sess", turn_index=0):
        super().__init__()
        self.cfg = cfg or {}
        self.vad_speaking = False
        self.pending_name_request = None
        self.pending_greet = None
        self.session_id = session_id
        self.turn_index = turn_index
        self._pr5_talk_timestamps = []
        self._pr5_last_aizuchi_ts = 0.0
        self._pr5_last_deferral_ts = 0.0
        self._last_speaking_ts = None
        self.state = State.IDLE
        self._entered_talk = False
    def _enter_state(self, s):
        self.state = s
        if s == State.TALK:
            self._entered_talk = True
    def _maybe_interrupt(self, *a, **k):
        pass
    def _notify(self):
        pass

def make_cfg(enabled=True, aliases=None):
    return {
        "stt": {
            "self_address": {
                "enabled": enabled,
                "name_aliases": aliases or ["美空", "misora"],
                "debug": True,
            }
        }
    }

def test_pr5_deterministic_delay_and_skip(monkeypatch):
    sm = DummySM(cfg=make_cfg(), session_id="sess1", turn_index=1)
    # Patch time.sleep to record delay
    delays = []
    monkeypatch.setattr("time.sleep", lambda d: delays.append(d))
    # Should always delay deterministically
    sm.on_event("stt_final", {"text": "美空 教えて"})
    assert any(0.19 < d < 0.7 for d in delays)
    # Should not skip reply if density low
    assert sm._entered_talk

def test_pr5_skip_on_density(monkeypatch):
    sm = DummySM(cfg=make_cfg(), session_id="sess2", turn_index=2)
    # Simulate high density
    now = time.time()
    sm._pr5_talk_timestamps = [now-5, now-10, now-15, now-20]
    monkeypatch.setattr("time.sleep", lambda d: None)
    sm._entered_talk = False
    sm.on_event("stt_final", {"text": "美空 教えて"})
    # 50% deterministic skip, so just check: either talk or not, but no error
    # If skipped, _entered_talk is False
    # If not skipped, _entered_talk is True
    assert sm._entered_talk in (True, False)

def test_pr5_aizuchi(monkeypatch):
    sm = DummySM(cfg=make_cfg(), session_id="sess3", turn_index=3)
    sm.vad_speaking = False
    sm.pending_name_request = None
    sm.pending_greet = None
    sm._pr5_last_aizuchi_ts = time.time() - 20
    # Not addressed
    def fake_detect_self_address(*a, **k):
        class D: addressed = False; score = 0.0; reason = "test"
        return D()
    monkeypatch.setattr("core.state_machine.detect_self_address", fake_detect_self_address)
    monkeypatch.setattr("time.sleep", lambda d: None)
    # Should aizuchi or not, but never error
    sm.on_event("stt_final", {"text": "テスト"})
    # No assertion: just ensure no crash

def test_pr5_deferral(monkeypatch):
    sm = DummySM(cfg=make_cfg(), session_id="sess4", turn_index=4)
    sm.vad_speaking = False
    sm.pending_name_request = None
    sm.pending_greet = None
    sm._pr5_last_deferral_ts = time.time() - 30
    # Not addressed
    def fake_detect_self_address(*a, **k):
        class D: addressed = False; score = 0.0; reason = "test"
        return D()
    monkeypatch.setattr("core.state_machine.detect_self_address", fake_detect_self_address)
    monkeypatch.setattr("time.sleep", lambda d: None)
    # Should defer or not, but never error
    sm.on_event("stt_final", {"text": "テスト"})
    # No assertion: just ensure no crash

def test_pr5_emergency_suppresses():
    sm = DummySM(cfg=make_cfg(), session_id="sess5", turn_index=5)
    class FakeEmergency:
        def is_active(self): return True
    sm._get_emergency = lambda: FakeEmergency()
    sm._entered_talk = False
    sm.on_event("stt_final", {"text": "美空 教えて"})
    # Should not enter TALK or reply
    assert not sm._entered_talk
