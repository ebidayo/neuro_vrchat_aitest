import pytest
from core.speaker_id import SpeakerID
from core.state_machine import StateMachine


def test_speakerid_mock_enroll_and_identify():
    sid = SpeakerID(backend="mock", threshold=0.5)
    sid.enroll("alice")
    # identify using the test convenience string 'as_name:alice'
    res = sid.identify("as_name:alice")
    assert res["speaker_id"] == "alice"
    assert res["matched"] is True
    assert res["confidence"] > 0.0


def test_speakerid_disabled_mode():
    sid = SpeakerID(backend="not_available_backend", threshold=0.5)
    # backend not implemented; should be disabled
    res = sid.identify(None)
    assert res["speaker_id"] is None
    assert res["matched"] is False


def test_state_machine_applies_speaker_focus_on_stt_final():
    sm = StateMachine()
    # configure threshold lower for testing
    sm.speaker_threshold = 0.5
    assert sm.active_speaker_id is None
    sm.on_event("stt_final", {"text": "hello", "speaker_id": "alice", "speaker_confidence": 0.8})
    assert sm.active_speaker_id == "alice"
    assert sm.social_pressure >= 0.2


def test_state_machine_ignores_low_confidence_speaker():
    sm = StateMachine()
    sm.speaker_threshold = 0.9
    sm.on_event("stt_final", {"text": "hello", "speaker_id": "bob", "speaker_confidence": 0.3})
    assert sm.active_speaker_id is None
