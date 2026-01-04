import pytest
import time
from core.memory.speaker_store import SpeakerStore

def test_record_and_recent():
    store = SpeakerStore(":memory:")
    k = "spk1"
    h1 = "hashA"
    h2 = "hashB"
    t1 = 1000
    t2 = 2000
    # First record
    store.record_avatar_hash(k, h1, t1)
    assert store.get_recent_avatar_hash(k) == h1
    # Second hash
    store.record_avatar_hash(k, h2, t2)
    assert store.get_recent_avatar_hash(k) == h2

def test_count_and_top():
    store = SpeakerStore(":memory:")
    k = "spk2"
    h1, h2 = "hashA", "hashB"
    t1, t2, t3 = 1000, 2000, 3000
    # Record h1 twice, h2 once
    store.record_avatar_hash(k, h1, t1)
    store.record_avatar_hash(k, h1, t2)
    store.record_avatar_hash(k, h2, t3)
    tops = store.get_top_avatar_hashes(k, limit=2)
    assert tops[0][0] == h1 and tops[0][1] == 2
    assert tops[1][0] == h2 and tops[1][1] == 1

def test_db_exception_soft():
    class DummyStore(SpeakerStore):
        def __init__(self):
            pass
        def _conn(self):
            raise RuntimeError("fail")
    s = SpeakerStore(":memory:")
    # forcibly close connection to simulate error
    s._conn.close()
    # Should not raise
    s.record_avatar_hash("spk", "hash", 123)
    assert s.get_recent_avatar_hash("spk") is None
    assert s.get_top_avatar_hashes("spk") == []
