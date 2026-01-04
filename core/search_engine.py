"""Minimal SearchEngine with cache and pluggable fetch for tests.

Provides search(query, sources=[]) which returns a dict with ok/from_cache/ts/items/error.
The default fetch is a dummy generator to avoid external network calls; tests can monkeypatch
_search to simulate real fetch behavior.
"""
import time
from typing import List, Tuple, Dict, Any
import hashlib
import json


class SearchEngine:
    def __init__(self, cache_ttl_sec: float = 1800.0, min_interval_sec: float = 60.0):
        self.cache_ttl_sec = float(cache_ttl_sec)
        self.min_interval_sec = float(min_interval_sec)
        # cache: key -> (result_dict, ts)
        self._cache: dict = {}
        self._last_call_ts: float = 0.0

    def _make_key(self, query: str, sources: List[str]) -> str:
        keyobj = (query or "", tuple(sorted(sources or [])))
        return hashlib.sha256(json.dumps(keyobj, ensure_ascii=False).encode("utf-8")).hexdigest()

    def _fetch(self, query: str, sources: List[str]) -> List[Dict[str, Any]]:
        """Default fake fetch: returns 3 dummy items. Override in tests."""
        # Simulate a network-bound fetch (fast dummy here)
        items = []
        for i in range(1, 4):
            items.append({
                "title": f"{query} - result {i}",
                "summary": f"Summary of {query} (item {i})",
                "url": f"https://example.com/{query.replace(' ', '_')}/{i}",
                "source": (sources[i % len(sources)] if sources else "web")
            })
        return items

    def search(self, query: str, *, sources: List[str] = None) -> Dict[str, Any]:
        now = time.time()
        # rate limiting
        if now - self._last_call_ts < self.min_interval_sec:
            return {"ok": False, "query": query, "items": [], "error": "rate_limited", "from_cache": False, "ts": now}

        key = self._make_key(query, sources or [])
        cached = self._cache.get(key)
        if cached:
            result, ts = cached
            if now - ts <= self.cache_ttl_sec:
                return {"ok": True, "query": query, "items": result, "error": None, "from_cache": True, "ts": ts}

        # perform fetch
        try:
            items = self._fetch(query, sources or [])
            self._cache[key] = (items, now)
            self._last_call_ts = now
            return {"ok": True, "query": query, "items": items, "error": None, "from_cache": False, "ts": now}
        except Exception as e:
            self._last_call_ts = now
            return {"ok": False, "query": query, "items": [], "error": str(e), "from_cache": False, "ts": now}
