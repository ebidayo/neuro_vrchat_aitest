import time

import pytest

from core.state_machine import StateMachine, State


def test_name_prompt_requires_streak():
    sm = StateMachine()
    sm.name_ask_min_streak = 2
    sm.name_ask_min_conf = 0.65

    # first stt_final with high conf -> should not create pending request yet
    sm.on_event("stt_final", {"text": "", "speaker_alias": "unknown_1", "speaker_confidence": 0.8})
    assert sm.pending_name_request is None

    # second consecutive stt_final with same alias and high conf -> should create pending
    sm.on_event("stt_final", {"text": "", "speaker_alias": "unknown_1", "speaker_confidence": 0.8})
    assert sm.pending_name_request is not None
    assert sm.pending_name_request.get("alias") == "unknown_1"


def test_name_prompt_not_counted_when_low_conf():
    sm = StateMachine()
    sm.name_ask_min_streak = 2
    sm.name_ask_min_conf = 0.65

    # two low-conf events should not accumulate streak
    sm.on_event("stt_final", {"text": "", "speaker_alias": "unknown_2", "speaker_confidence": 0.5})
    sm.on_event("stt_final", {"text": "", "speaker_alias": "unknown_2", "speaker_confidence": 0.5})
    assert sm.pending_name_request is None


def test_name_prompt_respects_min_interval():
    sm = StateMachine()
    sm.name_ask_min_streak = 2
    sm.name_ask_min_conf = 0.65
    sm.name_ask_min_interval_sec = 3.0

    # trigger first prompt
    sm.on_event("stt_final", {"text": "", "speaker_alias": "unknown_3", "speaker_confidence": 0.9})
    sm.on_event("stt_final", {"text": "", "speaker_alias": "unknown_3", "speaker_confidence": 0.9})
    assert sm.pending_name_request is not None

    # clear pending and simulate finishing ask
    sm.pending_name_request = None
    # immediate second stable detection should NOT prompt due to min interval
    sm.on_event("stt_final", {"text": "", "speaker_alias": "unknown_3", "speaker_confidence": 0.9})
    sm.on_event("stt_final", {"text": "", "speaker_alias": "unknown_3", "speaker_confidence": 0.9})
    # still no new pending because min interval applies
    assert sm.pending_name_request is None

    # advance time beyond min interval and try again -> should prompt
    sm._last_name_asked_at["unknown_3"] = time.time() - 10.0
    # also clear global last ask ts to avoid global cooldown blocking in test
    sm._last_name_request_ts = time.time() - 1000.0
    sm.on_event("stt_final", {"text": "", "speaker_alias": "unknown_3", "speaker_confidence": 0.9})
    sm.on_event("stt_final", {"text": "", "speaker_alias": "unknown_3", "speaker_confidence": 0.9})
    assert sm.pending_name_request is not None
