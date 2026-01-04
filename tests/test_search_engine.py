import time

from core.search_engine import SearchEngine


def test_search_cache_behavior():
    se = SearchEngine(cache_ttl_sec=60.0, min_interval_sec=0.0)

    # Monkeypatch _fetch to deterministic return
    def fake_fetch(q, sources):
        return [{"title": f"{q} result", "summary": "ok", "url": "http://x/1", "source": "web"}]

    se._fetch = fake_fetch

    r1 = se.search("alpha", sources=["web"])
    assert r1["ok"] is True
    assert r1["from_cache"] is False
    ts1 = r1["ts"]

    # immediate second should be from_cache
    r2 = se.search("alpha", sources=["web"])
    assert r2["ok"] is True
    assert r2["from_cache"] is True
    assert r2["ts"] == ts1

    # different query -> fresh
    r3 = se.search("beta", sources=["web"])
    assert r3["ok"] is True
    assert r3["from_cache"] is False
