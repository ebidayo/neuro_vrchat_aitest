import tempfile
import os
import time

import pytest

from core.memory.speaker_store import SpeakerStore
from core.state_machine import StateMachine, State


def test_speaker_store_crud(tmp_path):
    dbfile = tmp_path / "speaker_test.sqlite"
    s = SpeakerStore(db_path=str(dbfile))
    # set profile
    profile = s.set_profile("unknown_1", "たろう", consent=True)
    assert profile["display_name"] == "たろう"
    # touch seen
    ok = s.touch_seen("unknown_1")
    assert ok
    # re-open and confirm persistence
    s2 = SpeakerStore(db_path=str(dbfile))
    p2 = s2.get_profile_by_alias("unknown_1")
    assert p2 is not None
    assert p2["display_name"] == "たろう"
    # forget by alias
    okf = s2.forget_profile("unknown_1")
    assert okf
    assert s2.get_profile_by_alias("unknown_1") is None


def test_name_flow_state_machine():
    sm = StateMachine()
    # no pending initially
    assert sm.pending_name_request is None
    # stable detection via stt_final should create pending name request (requires streak)
    sm.on_event("stt_final", {"text": "", "speaker_alias": "unknown_1", "speaker_confidence": 0.85})
    sm.on_event("stt_final", {"text": "", "speaker_alias": "unknown_1", "speaker_confidence": 0.85})
    assert sm.pending_name_request is not None
    assert sm.pending_name_request.get("stage") == "ask"
    # simulate entering TALK (mid-speech) and then answer
    sm._enter_state(State.TALK)
    # user answers name
    sm.on_event("name_answer", {"alias": "unknown_1", "name": "たろう", "confidence": 0.9})
    assert sm.pending_name_request.get("stage") == "confirm"
    assert sm.pending_name_request.get("name_candidate") == "たろう"
    # user confirms
    sm.on_event("name_confirm_yes", {"alias": "unknown_1"})
    assert sm.pending_name_set is not None
    assert sm.pending_name_set.get("alias") == "unknown_1"
    assert sm.pending_name_set.get("name") == "たろう"
    # if user had said no
    sm2 = StateMachine()
    sm2.on_event("stt_final", {"text": "", "speaker_alias": "unknown_2", "speaker_confidence": 0.9})
    sm2.on_event("stt_final", {"text": "", "speaker_alias": "unknown_2", "speaker_confidence": 0.9})
    sm2.on_event("name_answer", {"alias": "unknown_2", "name": "花子", "confidence": 0.9})
    sm2.on_event("name_confirm_no", {"alias": "unknown_2"})
    assert sm2.pending_name_request.get("stage") == "retry"


def test_forget_and_save_workflow(tmp_path):
    dbfile = tmp_path / "speaker_flow.sqlite"
    store = SpeakerStore(db_path=str(dbfile))
    sm = StateMachine()
    # Simulate detection and confirm flow: sm will set pending_name_set
    # create pending via stable stt_final events
    sm.on_event("stt_final", {"text": "", "speaker_alias": "unknown_3", "speaker_confidence": 0.9})
    sm.on_event("stt_final", {"text": "", "speaker_alias": "unknown_3", "speaker_confidence": 0.9})
    sm.on_event("name_answer", {"alias": "unknown_3", "name": "次郎", "confidence": 0.95})
    sm.on_event("name_confirm_yes", {"alias": "unknown_3"})
    assert sm.pending_name_set is not None

    # main would persist this; simulate main persisting and then signaling saved ack
    pset = sm.pending_name_set
    store.set_profile(pset["alias"], pset["name"], consent=True)
    sm.pending_name_set = None
    sm.pending_name_saved = {"alias": pset["alias"], "name": pset["name"], "ts": time.time()}
    assert store.get_profile_by_alias("unknown_3")["display_name"] == "次郎"

    # forget by alias via store
    ok = store.forget_profile("unknown_3")
    assert ok
    assert store.get_profile_by_alias("unknown_3") is None
