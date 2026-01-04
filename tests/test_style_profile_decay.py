import time
from core.memory.speaker_store import SpeakerStore
from core.memory_decay import decay_factor
import tempfile
import os
import json

def make_profile(top_tokens, top_bigrams, filler, punct=None, politeness=None, length=None):
    return {
        "top_tokens": [{"t": t, "c": c} for t, c in top_tokens],
        "top_bigrams": [{"t": t, "c": c} for t, c in top_bigrams],
        "filler": [{"t": t, "c": c} for t, c in filler],
        "punct": punct or {},
        "politeness": politeness or {},
        "length": length or {},
    }

def test_style_profile_decayed_min_total_utt():
    store = SpeakerStore(':memory:')
    now = 1000000
    # total_utt_count=5 < min_total_utt_to_apply=8
    prof = make_profile([("a", 10)], [("b", 5)], [("c", 2)])
    c = store._conn.cursor()
    c.execute("INSERT INTO speaker_style_profile (speaker_key, updated_ts, total_utt_count, profile_json) VALUES (?,?,?,?)",
              ("user1", now-100, 5, json.dumps(prof)))
    store._conn.commit()
    out = store.get_style_profile_decayed("user1", now, 86400, 0.2, min_total_utt_to_apply=8)
    # 減衰しない
    assert out["top_tokens"][0]["c"] == 10
    store._conn.close()

def test_style_profile_decayed_decay():
    store = SpeakerStore(':memory:')
    now = 1000000
    prof = make_profile([("a", 10), ("b", 5)], [("c", 8)], [("d", 4)])
    c = store._conn.cursor()
    c.execute("INSERT INTO speaker_style_profile (speaker_key, updated_ts, total_utt_count, profile_json) VALUES (?,?,?,?)",
              ("user2", now-100, 20, json.dumps(prof)))
    store._conn.commit()
    # dt=100, half_life=100 -> factor=0.5
    out = store.get_style_profile_decayed("user2", now, 100, 0.1, min_total_utt_to_apply=8)
    # a: 10*0.5=5, b:5*0.5=2.5->2, c:8*0.5=4, d:4*0.5=2
    assert out["top_tokens"][0]["c"] == 5
    assert out["top_tokens"][1]["c"] == 2
    assert out["top_bigrams"][0]["c"] == 4
    assert out["filler"][0]["c"] == 2
    # 決定的: c desc, t asc
    assert out["top_tokens"] == sorted(out["top_tokens"], key=lambda x: (-x["c"], x["t"]))
    store._conn.close()

def test_style_profile_decayed_dt0():
    store = SpeakerStore(':memory:')
    now = 1000000
    prof = make_profile([("a", 10)], [("b", 5)], [("c", 2)])
    c = store._conn.cursor()
    c.execute("INSERT INTO speaker_style_profile (speaker_key, updated_ts, total_utt_count, profile_json) VALUES (?,?,?,?)",
              ("user3", now, 10, json.dumps(prof)))
    store._conn.commit()
    out = store.get_style_profile_decayed("user3", now, 100, 0.1, min_total_utt_to_apply=8)
    # dt=0, factor=1
    assert out["top_tokens"][0]["c"] == 10
    store._conn.close()

def test_style_profile_decayed_sorting():
    store = SpeakerStore(':memory:')
    now = 1000000
    prof = make_profile([("b", 5), ("a", 5)], [], [])
    c = store._conn.cursor()
    c.execute("INSERT INTO speaker_style_profile (speaker_key, updated_ts, total_utt_count, profile_json) VALUES (?,?,?,?)",
              ("user4", now-100, 20, json.dumps(prof)))
    store._conn.commit()
    out = store.get_style_profile_decayed("user4", now, 100, 0.1, min_total_utt_to_apply=8)
    # 同点はt昇順
    assert out["top_tokens"][0]["t"] == "a" or out["top_tokens"][0]["t"] == "b"
    assert out["top_tokens"] == sorted(out["top_tokens"], key=lambda x: (-x["c"], x["t"]))
    store._conn.close()
