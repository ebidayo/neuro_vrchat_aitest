from dataclasses import dataclass
from typing import List, Optional
import time
import threading

@dataclass(frozen=True)
class AliasEntry:
    alias: str
    weight: float
    last_seen_ts: float
    count: int
    confirmed: bool

class LearnedAliasStore:
    def get_all(self) -> List[AliasEntry]:
        raise NotImplementedError
    def upsert(self, alias: str, weight: float, last_seen_ts: float, count: int) -> None:
        raise NotImplementedError
    def prune(self, now_ts: float) -> None:
        raise NotImplementedError

class InMemoryLearnedAliasStore(LearnedAliasStore):
    def __init__(self, max_entries=64):
        self._lock = threading.Lock()
        self._entries = {}
        self._max_entries = max_entries
    def get(self, alias: str) -> Optional[AliasEntry]:
        with self._lock:
            return self._entries.get(alias)

    def get_all(self) -> List[AliasEntry]:
        with self._lock:
            return sorted(self._entries.values(), key=lambda e: (-e.last_seen_ts, e.alias))

    def upsert(self, entry: AliasEntry) -> None:
        with self._lock:
            self._entries[entry.alias] = entry

    def prune(self, now_ts: float, max_entries: int = None, drop_below: float = 0.05, decay_tau_sec: float = None) -> None:
        with self._lock:
            # Drop entries with weight < drop_below
            self._entries = {k: v for k, v in self._entries.items() if v.weight >= drop_below}
            # Keep max_entries newest by last_seen_ts, tie-break by alias
            max_e = max_entries if max_entries is not None else self._max_entries
            all_sorted = sorted(self._entries.values(), key=lambda e: (-e.last_seen_ts, e.alias))
            self._entries = {e.alias: e for e in all_sorted[:max_e]}

try:
    import sqlite3
    class SqliteLearnedAliasStore(LearnedAliasStore):
        def __init__(self, path, max_entries=64):
            self._path = path
            self._max_entries = max_entries
            self._lock = threading.Lock()
            self._init_db()
        def _init_db(self):
            with sqlite3.connect(self._path) as conn:
                conn.execute("""
                CREATE TABLE IF NOT EXISTS alias (
                    alias TEXT PRIMARY KEY,
                    weight REAL,
                    last_seen_ts REAL,
                    count INTEGER
                )
                """)
        def get_all(self) -> List[AliasEntry]:
            with self._lock, sqlite3.connect(self._path) as conn:
                rows = conn.execute("SELECT alias, weight, last_seen_ts, count FROM alias").fetchall()
                result = [AliasEntry(a, round(w, 4), ts, c, w >= 0.6) for a, w, ts, c in rows]
                return sorted(result, key=lambda e: (-e.last_seen_ts, e.alias))
        def upsert(self, alias: str, weight: float, last_seen_ts: float, count: int) -> None:
            with self._lock, sqlite3.connect(self._path) as conn:
                conn.execute(
                    "INSERT INTO alias (alias, weight, last_seen_ts, count) VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(alias) DO UPDATE SET weight=excluded.weight, last_seen_ts=excluded.last_seen_ts, count=excluded.count",
                    (alias, round(weight, 4), last_seen_ts, count)
                )
        def prune(self, now_ts: float) -> None:
            with self._lock, sqlite3.connect(self._path) as conn:
                # Drop entries with weight < 0.05
                conn.execute("DELETE FROM alias WHERE weight < 0.05")
                # Keep max_entries newest by last_seen_ts, tie-break by alias
                rows = conn.execute("SELECT alias FROM alias ORDER BY last_seen_ts DESC, alias ASC").fetchall()
                keep = set(a for (a,) in rows[:self._max_entries])
                conn.execute("DELETE FROM alias WHERE alias NOT IN (%s)" % ','.join('?'*len(keep)), tuple(keep))
except Exception:
    SqliteLearnedAliasStore = None  # fail-soft fallback
