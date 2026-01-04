import pytest
from core.memory.speaker_store import SpeakerStore
from core.agent_interest_store import AgentInterestStore

def test_bump_interest_insert():
    store = SpeakerStore(":memory:")
    interest = AgentInterestStore(store)
    now = 1000000
    interest.bump_interest("topic1", now, 1.0)
    c = store._conn.cursor()
    row = c.execute("SELECT score, last_seen_ts FROM agent_interest WHERE topic=?", ("topic1",)).fetchone()
    assert row is not None
    assert abs(row[0] - 1.0) < 1e-6
    assert row[1] == now
    store._conn.close()

def test_bump_interest_update_retention():
    store = SpeakerStore(":memory:")
    interest = AgentInterestStore(store)
    now = 1000000
    interest.bump_interest("topic1", now, 1.0)
    interest.bump_interest("topic1", now+10, 2.0)
    c = store._conn.cursor()
    row = c.execute("SELECT score, last_seen_ts FROM agent_interest WHERE topic=?", ("topic1",)).fetchone()
    # score = 1.0*0.98 + 2.0 = 2.98
    assert abs(row[0] - 2.98) < 1e-6
    assert row[1] == now+10
    store._conn.close()

def test_get_interest_weights_decayed_boost_and_decay():
    store = SpeakerStore(":memory:")
    interest = AgentInterestStore(store)
    now = 1000000
    base = {"topic1": 1.0, "topic2": 2.0}
    # topic1: score=10, last_seen=now-100 (新しい)
    # topic2: score=10, last_seen=now-1000 (古い)
    c = store._conn.cursor()
    c.execute("INSERT INTO agent_interest (topic, last_seen_ts, score) VALUES (?,?,?)", ("topic1", now-100, 10.0))
    c.execute("INSERT INTO agent_interest (topic, last_seen_ts, score) VALUES (?,?,?)", ("topic2", now-1000, 10.0))
    store._conn.commit()
    out = interest.get_interest_weights_decayed(now, base, half_life_sec=200, floor_weight=0.1)
    # topic1は新しいのでboost大、topic2は古いのでboost小
    boost1 = out["topic1"] - base["topic1"]
    boost2 = out["topic2"] - base["topic2"]
    assert boost1 > boost2
    # clamp範囲内
    assert 0.5 <= out["topic1"] <= 2.0
    assert 1.0 <= out["topic2"] <= 4.0
    store._conn.close()

def test_get_interest_weights_decayed_clamp():
    store = SpeakerStore(":memory:")
    interest = AgentInterestStore(store)
    now = 1000000
    base = {"topic1": 1.0}
    c = store._conn.cursor()
    c.execute("INSERT INTO agent_interest (topic, last_seen_ts, score) VALUES (?,?,?)", ("topic1", now-10, 100.0))
    store._conn.commit()
    out = interest.get_interest_weights_decayed(now, base, half_life_sec=100, floor_weight=0.1, max_boost=0.6, clamp_min_mul=0.5, clamp_max_mul=2.0)
    # clamp上限
    assert out["topic1"] <= 2.0
    # clamp下限
    c.execute("UPDATE agent_interest SET score=0.0 WHERE topic=?", ("topic1",))
    store._conn.commit()
    out2 = interest.get_interest_weights_decayed(now, base, half_life_sec=100, floor_weight=0.1)
    assert out2["topic1"] >= 0.5
    store._conn.close()

def test_get_interest_weights_decayed_db_error():
    store = SpeakerStore(":memory:")
    interest = AgentInterestStore(store)
    now = 1000000
    base = {"topic1": 1.0}
    store._conn.close()  # 強制エラー
    out = interest.get_interest_weights_decayed(now, base, 100, 0.1)
    assert out == base
