import time
from core import speech_brain
from core.state_machine import StateMachine, State


def test_build_idle_presence_plan_one_chunk():
    scalars = {"text": "…", "arousal": 0.3, "look": 0.5}
    plan = speech_brain.build_idle_presence_plan(scalars)
    assert isinstance(plan, dict)
    sp = plan.get("speech_plan")
    assert isinstance(sp, list) and len(sp) == 1
    c = sp[0]
    assert c.get("type") in ("think", "aside", "pause", "self_correct")
    assert c.get("osc", {}).get("N_State") == "IDLE"


def test_build_starter_plan_one_chunk_and_short():
    scalars = {"text": "ちょっと聞いていい？", "arousal": 0.5, "look": 0.8}
    plan = speech_brain.build_starter_plan(scalars)
    sp = plan.get("speech_plan")
    assert isinstance(sp, list) and len(sp) == 1
    c = sp[0]
    assert c.get("type") in ("say", "question")
    assert 1 <= len(c.get("text", "")) <= 16
    assert c.get("osc", {}).get("N_State") == "TALK"


def test_starter_not_fired_during_search_or_alert():
    sm = StateMachine()
    sm.state = State.SEARCH
    sm.social_pressure = 0.8
    sm.confidence = 0.9
    sm._last_starter_ts = 0
    sm._tick(1.0)
    assert sm.pending_starter is None

    sm.state = State.ALERT
    sm._tick(1.0)
    assert sm.pending_starter is None


def test_starter_cooldown_respected():
    sm = StateMachine()
    sm.state = State.IDLE
    sm.social_pressure = 0.8
    sm.confidence = 0.9
    sm._last_speaking_ts = time.time() - 10
    # set last starter recent
    sm._last_starter_ts = time.time()
    sm._tick(1.0)
    assert sm.pending_starter is None

    # set last starter long ago
    sm._last_starter_ts = time.time() - (sm.starter_cooldown + 1)
    sm._tick(1.0)
    # starter should fire and transition to TALK
    assert sm.pending_starter is not None
    assert sm.state == State.TALK
