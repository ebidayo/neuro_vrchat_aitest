import pytest
from debate import can_debate

def test_no_debate_when_not_addressed():
    ctx = {
        "behavior_mode": "TALK_PRIMARY",
        "addressed": False,
        "response_strength": "low",
        "text": "寿司は最高だ",
        "emergency": type("E", (), {"is_active": lambda self: False})(),
        "topic": "食べ物"
    }
    assert not can_debate(ctx)
