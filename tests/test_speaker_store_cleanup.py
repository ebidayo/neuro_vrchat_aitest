import pytest
from core.memory.speaker_store import SpeakerStore

def test_cleanup_news():
    store = SpeakerStore(":memory:")
    now = 1000000
    c = store._conn.cursor()
    # 2件: 1つはTTL内、1つはTTL外
    c.execute("INSERT INTO news_items (id, source, title, url, published_ts, fetched_ts, summary, topic_key) VALUES (?,?,?,?,?,?,?,?)",
              ("a", "src", "t", "u", now-100, now-100, "s", "tech"))
    c.execute("INSERT INTO news_items (id, source, title, url, published_ts, fetched_ts, summary, topic_key) VALUES (?,?,?,?,?,?,?,?)",
              ("b", "src", "t", "u", now-10, now-10, "s", "tech"))
    store._conn.commit()
    deleted = store.cleanup_news(now, ttl_sec=50)
    # aは消える、bは残る
    left = c.execute("SELECT COUNT(*) FROM news_items").fetchone()[0]
    assert deleted == 1
    assert left == 1
    store._conn.close()

def test_cleanup_kb():
    store = SpeakerStore(":memory:")
    now = 1000000
    c = store._conn.cursor()
    c.execute("INSERT INTO kb_snippets (id, source, query, url, fetched_ts, snippet) VALUES (?,?,?,?,?,?)",
              ("a", "src", "q", "u", now-100, "s"))
    c.execute("INSERT INTO kb_snippets (id, source, query, url, fetched_ts, snippet) VALUES (?,?,?,?,?,?)",
              ("b", "src", "q", "u", now-10, "s"))
    store._conn.commit()
    deleted = store.cleanup_kb(now, ttl_sec=50)
    left = c.execute("SELECT COUNT(*) FROM kb_snippets").fetchone()[0]
    assert deleted == 1
    assert left == 1
    store._conn.close()

def test_cleanup_agent_interest():
    store = SpeakerStore(":memory:")
    now = 1000000
    c = store._conn.cursor()
    # 3件: 1つはscore大, 1つはscore小で古い, 1つはscore小で新しい
    c.execute("INSERT INTO agent_interest (topic, last_seen_ts, score) VALUES (?,?,?)", ("a", now-100, 0.1))
    c.execute("INSERT INTO agent_interest (topic, last_seen_ts, score) VALUES (?,?,?)", ("b", now-100, 0.5))
    c.execute("INSERT INTO agent_interest (topic, last_seen_ts, score) VALUES (?,?,?)", ("c", now-10, 0.1))
    store._conn.commit()
    deleted = store.cleanup_agent_interest(now, ttl_sec=50, min_score=0.2)
    # aだけ消える
    left = c.execute("SELECT COUNT(*) FROM agent_interest").fetchone()[0]
    assert deleted == 1
    assert left == 2
    store._conn.close()
