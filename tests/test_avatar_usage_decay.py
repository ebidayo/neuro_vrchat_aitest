import time
import pytest
from core.memory.speaker_store import SpeakerStore
from core.memory_decay import apply_decay_to_counts

def setup_avatar_usage(store, speaker_key, items):
    c = store._conn.cursor()
    for avatar_hash, seen_count, last_seen_ts in items:
        c.execute("INSERT INTO avatar_usage (speaker_key, avatar_hash, first_seen_ts, last_seen_ts, seen_count) VALUES (?,?,?,?,?)",
                  (speaker_key, avatar_hash, last_seen_ts, last_seen_ts, seen_count))
    store._conn.commit()

def test_avatar_usage_decay_order():
    store = SpeakerStore(":memory:")
    now = 1000000
    # avatar1: seen_count=10, last_seen_ts=now-1000
    # avatar2: seen_count=5, last_seen_ts=now-10 (recent)
    setup_avatar_usage(store, "user1", [
        ("avatar1", 10, now-1000),
        ("avatar2", 5, now-10),
    ])
    out = store.get_top_avatar_hashes_decayed("user1", 2, now, half_life_sec=100, floor_weight=0.1)
    # recent low-count can overtake old high-count
    assert out[0][0] == "avatar2"
    assert out[1][0] == "avatar1"
    store._conn.close()

def test_avatar_usage_decay_sorting():
    store = SpeakerStore(":memory:")
    now = 1000000
    setup_avatar_usage(store, "user2", [
        ("a", 5, now-100),
        ("b", 5, now-100),
        ("c", 5, now-100),
    ])
    out = store.get_top_avatar_hashes_decayed("user2", 3, now, 100, 0.1)
    # tie: token asc
    assert [x[0] for x in out] == ["a", "b", "c"]
    store._conn.close()

def test_avatar_usage_decay_db_error():
    store = SpeakerStore(":memory:")
    # forcibly close connection to simulate DB error
    store._conn.close()
    out = store.get_top_avatar_hashes_decayed("user3", 2, 1000000, 100, 0.1)
    assert out == []
