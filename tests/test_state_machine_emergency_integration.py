import pytest
from core.state_machine import StateMachine, State

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

class FakeChatbox:
    def __init__(self):
        self.outputs = []
    def output(self, msg):
        self.outputs.append(msg)

class FakeLogger:
    def info(self, *a, **k):
        pass

def make_cfg():
    return {
        "emergency": {
            "enabled": True,
            "cooldown_sec": 10.0,
            "beep_wav_path": "assets/beep.wav",
            "force_language_ja": True,
            "active_hold_sec": 10.0,
        }
    }

def make_sm():
    sm = StateMachine()
    sm.cfg = make_cfg()
    sm.clock = FakeClock()
    sm.logger = FakeLogger()
    sm.beep_player = FakeBeepPlayer()
    sm.chatbox = FakeChatbox()
    return sm

def test_emergency_trigger_preempts_talk():
    sm = make_sm()
    sm.state = State.TALK
    sm.on_event("emergency_trigger", {"message_ja": "地震です", "reason": "test"})
    assert sm.state == State.ALERT
    assert sm.chatbox.outputs[-1] == "地震です"

def test_stt_suppressed_during_emergency():
    sm = make_sm()
    sm.state = State.TALK
    sm.on_event("emergency_trigger", {"message_ja": "地震です", "reason": "test"})
    # Now emergency is active
    sm.on_event("stt_final", {"text": "何か話して"})
    # State should remain ALERT, no TALK
    assert sm.state == State.ALERT
    # No error, no output added
    assert sm.chatbox.outputs[-1] == "地震です"

def test_content_change_bypass():
    sm = make_sm()
    sm.state = State.TALK
    sm.on_event("emergency_trigger", {"message_ja": "地震です", "reason": "test"})
    sm.clock.advance(2)
    sm.on_event("emergency_trigger", {"message_ja": "津波です", "reason": "test"})
    # Both messages should be output
    assert sm.chatbox.outputs == ["地震です", "津波です"]
    # Beep called twice
    assert len(sm.beep_player.calls) == 2

def test_beep_fail_soft():
    sm = make_sm()
    sm.beep_player = None  # Remove beep player
    sm.state = State.TALK
    sm.on_event("emergency_trigger", {"message_ja": "地震です", "reason": "test"})
    # Should still output message, no exception
    assert sm.chatbox.outputs[-1] == "地震です"

def test_opinion_suppressed_flag():
    sm = make_sm()
    sm.state = State.TALK
    sm.on_event("emergency_trigger", {"message_ja": "地震です", "reason": "test"})
    assert sm.is_opinion_suppressed()
    sm.clock.advance(20)
    # After emergency window, should be False
    assert not sm.is_opinion_suppressed()
