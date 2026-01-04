import time

from core.memory.speaker_store import SpeakerStore
from core.state_machine import StateMachine, State


def test_known_speaker_greet():
    store = SpeakerStore(db_path=":memory:")
    store.set_profile("unknown_1", "たろう", consent=True)

    sm = StateMachine()
    # simulate stt_final with known profile; indicate has_profile and provide speaker_key
    from datetime import datetime
    # pass now_dt so greet_type is deterministic in test
    now_dt = datetime(2026, 1, 1, 6, 0, 0)
    sm.on_event("stt_final", {"text": "", "speaker_alias": "unknown_1", "speaker_confidence": 0.9, "has_profile": True, "speaker_key": "spk:unknown_1", "display_name": "たろう", "now_dt": now_dt})
    sm.on_event("stt_final", {"text": "", "speaker_alias": "unknown_1", "speaker_confidence": 0.9, "has_profile": True, "speaker_key": "spk:unknown_1", "display_name": "たろう", "now_dt": now_dt})
    assert sm.pending_greet is not None
    assert sm.pending_greet.get("alias") == "unknown_1"
    assert sm.pending_greet.get("greet_type") == "morning"


def test_greet_cooldown():
    store = SpeakerStore(db_path=":memory:")
    store.set_profile("unknown_2", "花子", consent=True)

    sm = StateMachine()
    sm.on_event("stt_final", {"text": "", "speaker_alias": "unknown_2", "speaker_confidence": 0.9, "has_profile": True, "speaker_key": "spk:unknown_2", "display_name": "花子"})
    sm.on_event("stt_final", {"text": "", "speaker_alias": "unknown_2", "speaker_confidence": 0.9, "has_profile": True, "speaker_key": "spk:unknown_2", "display_name": "花子"})
    assert sm.pending_greet is not None
    # clear and attempt immediate second greeting
    sm.pending_greet = None
    sm.on_event("stt_final", {"text": "", "speaker_alias": "unknown_2", "speaker_confidence": 0.9, "has_profile": True, "speaker_key": "spk:unknown_2", "display_name": "花子"})
    sm.on_event("stt_final", {"text": "", "speaker_alias": "unknown_2", "speaker_confidence": 0.9, "has_profile": True, "speaker_key": "spk:unknown_2", "display_name": "花子"})
    assert sm.pending_greet is None


def test_no_greet_for_low_conf_or_unknown():
    store = SpeakerStore(db_path=":memory:")
    # unknown/no profile
    sm = StateMachine()
    sm.on_event("stt_final", {"text": "", "speaker_alias": "unknown_3", "speaker_confidence": 0.9, "has_profile": False})
    sm.on_event("stt_final", {"text": "", "speaker_alias": "unknown_3", "speaker_confidence": 0.9, "has_profile": False})
    assert sm.pending_greet is None
    # low confidence
    store.set_profile("unknown_4", "次郎", consent=True)
    sm2 = StateMachine()
    sm2.on_event("stt_final", {"text": "", "speaker_alias": "unknown_4", "speaker_confidence": 0.5, "has_profile": True, "speaker_key": "spk:unknown_4", "display_name": "次郎"})
    sm2.on_event("stt_final", {"text": "", "speaker_alias": "unknown_4", "speaker_confidence": 0.5, "has_profile": True, "speaker_key": "spk:unknown_4", "display_name": "次郎"})
    assert sm2.pending_greet is None


def test_greet_suppressed_during_search_or_alert():
    store = SpeakerStore(db_path=":memory:")
    store.set_profile("unknown_5", "五郎", consent=True)

    sm = StateMachine()
    # set state to SEARCH and ensure no greet
    sm._enter_state(State.SEARCH)
    sm.on_event("stt_final", {"text": "", "speaker_alias": "unknown_5", "speaker_confidence": 0.9, "has_profile": True, "speaker_key": "spk:unknown_5", "display_name": "五郎"})
    sm.on_event("stt_final", {"text": "", "speaker_alias": "unknown_5", "speaker_confidence": 0.9, "has_profile": True, "speaker_key": "spk:unknown_5", "display_name": "五郎"})
    assert sm.pending_greet is None
    # alert
    sm2 = StateMachine()
    sm2._enter_state(State.ALERT)
    sm2.on_event("stt_final", {"text": "", "speaker_alias": "unknown_5", "speaker_confidence": 0.9, "has_profile": True, "speaker_key": "spk:unknown_5", "display_name": "五郎"})
    sm2.on_event("stt_final", {"text": "", "speaker_alias": "unknown_5", "speaker_confidence": 0.9, "has_profile": True, "speaker_key": "spk:unknown_5", "display_name": "五郎"})
    assert sm2.pending_greet is None
