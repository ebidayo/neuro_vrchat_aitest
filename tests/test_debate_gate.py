import pytest
from debate import can_debate

class DummyEmergency:
    def is_active(self):
        return False

def test_can_debate_true():
    ctx = {
        "behavior_mode": "TALK_PRIMARY",
        "addressed": True,
        "response_strength": "high",
        "text": "寿司は最高だ",
        "emergency": DummyEmergency(),
        "topic": "食べ物"
    }
    assert can_debate(ctx)

def test_denylist_blocks():
    ctx = {
        "behavior_mode": "TALK_PRIMARY",
        "addressed": True,
        "response_strength": "high",
        "text": "選挙は大事だ",
        "emergency": DummyEmergency(),
        "topic": "選挙"
    }
    assert not can_debate(ctx)

def test_emergency_blocks():
    class E: def is_active(self): return True
    ctx = {
        "behavior_mode": "TALK_PRIMARY",
        "addressed": True,
        "response_strength": "high",
        "text": "寿司は最高だ",
        "emergency": E(),
        "topic": "食べ物"
    }
    assert not can_debate(ctx)

def test_not_addressed_blocks():
    ctx = {
        "behavior_mode": "TALK_PRIMARY",
        "addressed": False,
        "response_strength": "low",
        "text": "寿司は最高だ",
        "emergency": DummyEmergency(),
        "topic": "食べ物"
    }
    assert not can_debate(ctx)
