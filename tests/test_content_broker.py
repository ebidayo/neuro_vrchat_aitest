import time
import pytest
from core.content_broker import ContentBroker

def make_item(kind, id, topic, published_ts, confidence=0.7):
    return {
        "kind": kind,
        "id": id,
        "title": f"{topic}タイトル",
        "url": f"http://ex.com/{id}",
        "summary": f"{topic}要約",
        "topic": topic,
        "published_ts": published_ts,
        "fetched_ts": published_ts,
        "confidence": confidence,
    }

@pytest.fixture
def config():
    return {
        "content_broker": {
            "enabled": True,
            "max_pending": 20,
            "max_idle_pending": 30,
            "used_ttl_sec": 1000,
            "session_max_emits": 1,
            "emit_cooldown_sec": 100,
            "talk_cooldown_after_end_sec": 10,
            "min_confidence": 0.55,
            "max_social_pressure": 0.65,
            "max_arousal": 0.85,
            "require_idle_state": True,
            "allow_during_group_mode": True,
            "idle_aside": {
                "enabled": True,
                "emit_cooldown_sec": 5,
                "session_max_emits": 2,
                "min_confidence": 0.35,
                "max_social_pressure": 0.85,
            },
            "interest": {
                "enabled": True,
                "weights": {
                    "tech": 1.0,
                    "game": 1.4,
                    "anime": 1.3,
                    "disaster": 1.1,
                    "society": 0.9,
                    "other": 0.7,
                },
                "unknown_topic": "other",
                "drop_threshold": 0.15,
            },
        }
    }

def test_talk_cooldown(config):
    cb = ContentBroker(config)
    now = 1000
    cb.add_items([make_item("news","a","tech",now)], now_ts=now)
    cb.notify_talk_end(now)
    scalars = {"confidence":1.0,"social_pressure":0.0,"arousal":0.0}
    assert not cb.should_emit(now+5, scalars, "IDLE")
    assert cb.should_emit(now+15, scalars, "IDLE")

def test_session_max_emits(config):
    cb = ContentBroker(config)
    now = 1000
    cb.add_items([make_item("news","a","tech",now)], now_ts=now)
    scalars = {"confidence":1.0,"social_pressure":0.0,"arousal":0.0}
    assert cb.should_emit(now+20, scalars, "IDLE")
    cb.pop_for_conversation(now+20)
    assert not cb.should_emit(now+30, scalars, "IDLE")

def test_emit_cooldown(config):
    cfg2 = dict(config)
    cfg2["content_broker"] = dict(config["content_broker"])
    cfg2["content_broker"]["session_max_emits"] = 2
    cb = ContentBroker(cfg2)
    now = 1000
    cb.add_items([
        make_item("news","a","tech",now),
        make_item("news","b","game",now+1)
    ], now_ts=now)
    scalars = {"confidence":1.0,"social_pressure":0.0,"arousal":0.0}
    assert cb.should_emit(now+20, scalars, "IDLE")
    cb.pop_for_conversation(now+20)
    assert not cb.should_emit(now+100, scalars, "IDLE")
    assert cb.should_emit(now+121, scalars, "IDLE")
    cb.pop_for_conversation(now+121)
    assert not cb.should_emit(now+200, scalars, "IDLE")

def test_scalars_gating(config):
    cb = ContentBroker(config)
    now = 1000
    cb.add_items([make_item("news","a","tech",now)])
    s = {"confidence":0.5,"social_pressure":0.0,"arousal":0.0}
    assert not cb.should_emit(now+20, s, "IDLE")
    s = {"confidence":1.0,"social_pressure":0.7,"arousal":0.0}
    assert not cb.should_emit(now+20, s, "IDLE")
    s = {"confidence":1.0,"social_pressure":0.0,"arousal":0.9}
    assert not cb.should_emit(now+20, s, "IDLE")

def test_interest_scoring(config):
    cb = ContentBroker(config)
    now = 1000
    items = [
        make_item("news","a","game",now),
        make_item("news","b","tech",now),
        make_item("news","c","anime",now),
    ]
    cb.add_items(items, now_ts=now)
    # game(1.4) > anime(1.3) > tech(1.0)
    out = [cb.pop_for_conversation(now+20), cb.pop_for_conversation(now+121), cb.pop_for_conversation(now+250)]
    assert [i["topic"] for i in out if i] == ["game","anime","tech"]

def test_idle_aside(config):
    cb = ContentBroker(config)
    now = 1000
    cb.add_items([
        make_item("news","a","tech",now),
        make_item("news","b","game",now+1)
    ], now_ts=now)
    assert cb.pop_for_idle_aside(now_ts=now)
    assert not cb.pop_for_idle_aside(now_ts=now+1)
    assert cb.pop_for_idle_aside(now_ts=now+6)
    assert not cb.pop_for_idle_aside(now_ts=now+7)

def test_determinism(config):
    cb1 = ContentBroker(config)
    cb2 = ContentBroker(config)
    now = 1000
    items = [
        make_item("news","a","game",now),
        make_item("news","b","tech",now),
        make_item("news","c","anime",now),
    ]
    cb1.add_items(items, now_ts=now)
    cb2.add_items(items, now_ts=now)
    outs1 = [cb1.pop_for_conversation(now_ts=now+20), cb1.pop_for_conversation(now_ts=now+121), cb1.pop_for_conversation(now_ts=now+250)]
    outs2 = [cb2.pop_for_conversation(now_ts=now+20), cb2.pop_for_conversation(now_ts=now+121), cb2.pop_for_conversation(now_ts=now+250)]
    assert [i["id"] for i in outs1 if i] == [i["id"] for i in outs2 if i]
