"""Persistent speaker profile store.

Simple SQLite-backed store implementing the API described in the spec:
- get_profile_by_alias(alias) -> dict|None
- set_profile(alias, display_name, consent=True)
- forget_profile(alias) / forget_by_name(name)
- touch_seen(alias)

Designed to be lightweight and easily testable (accepts :memory: or a file path).
"""
from __future__ import annotations


import sqlite3
import time
from typing import Optional, Dict, List
import os
from core.memory.avatar_store import AvatarStore

SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS speaker_profiles (
        speaker_key TEXT PRIMARY KEY,
        display_name TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        last_seen_at TEXT,
        notes TEXT,
        consent INTEGER NOT NULL DEFAULT 1
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS speaker_alias (
        alias TEXT PRIMARY KEY,
        speaker_key TEXT NOT NULL,
        FOREIGN KEY(speaker_key) REFERENCES speaker_profiles(speaker_key)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS avatar_usage (
        speaker_key TEXT NOT NULL,
        avatar_hash TEXT NOT NULL,
        first_seen_ts INTEGER NOT NULL,
        last_seen_ts INTEGER NOT NULL,
        seen_count INTEGER NOT NULL,
        PRIMARY KEY (speaker_key, avatar_hash)
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_avatar_usage_speaker_last
      ON avatar_usage (speaker_key, last_seen_ts);
    """,
        """
        CREATE TABLE IF NOT EXISTS agent_interest (
            topic TEXT PRIMARY KEY,
            last_seen_ts INTEGER NOT NULL,
            score REAL NOT NULL
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_agent_interest_last
            ON agent_interest (last_seen_ts);
        """,
        """
        CREATE TABLE IF NOT EXISTS news_items (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            published_ts INTEGER NOT NULL,
            fetched_ts INTEGER NOT NULL,
            summary TEXT NOT NULL,
            topic_key TEXT NOT NULL
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_news_items_topic
            ON news_items (topic_key, published_ts);
        """,
        """
        CREATE TABLE IF NOT EXISTS kb_snippets (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            query TEXT NOT NULL,
            url TEXT NOT NULL,
            fetched_ts INTEGER NOT NULL,
            snippet TEXT NOT NULL
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS speaker_style_profile (
            speaker_key TEXT PRIMARY KEY,
            updated_ts INTEGER NOT NULL,
            total_utt_count INTEGER NOT NULL,
            profile_json TEXT NOT NULL
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_style_profile_updated
            ON speaker_style_profile (updated_ts);
        """,
]


class SpeakerStore:
    def cleanup_news(self, now_ts: int, ttl_sec: int) -> int:
        """news_itemsのTTL超過を削除。削除件数を返す。fail-soft。"""
        try:
            c = self._conn.cursor()
            cutoff = now_ts - ttl_sec
            res = c.execute("DELETE FROM news_items WHERE fetched_ts < ?", (cutoff,))
            self._conn.commit()
            return res.rowcount if hasattr(res, 'rowcount') else 0
        except Exception as e:
            logger = getattr(self, 'logger', None)
            if logger:
                logger.debug(f"cleanup_news failed: {e}")
            return 0
    def cleanup_kb(self, now_ts: int, ttl_sec: int) -> int:
        """kb_snippetsのTTL超過を削除。削除件数を返す。fail-soft。"""
        try:
            c = self._conn.cursor()
            cutoff = now_ts - ttl_sec
            res = c.execute("DELETE FROM kb_snippets WHERE fetched_ts < ?", (cutoff,))
            self._conn.commit()
            return res.rowcount if hasattr(res, 'rowcount') else 0
        except Exception as e:
            logger = getattr(self, 'logger', None)
            if logger:
                logger.debug(f"cleanup_kb failed: {e}")
            return 0

    def cleanup_agent_interest(self, now_ts: int, ttl_sec: int, min_score: float = 0.2) -> int:
        """agent_interestの古くてscore小さい行を削除。削除件数を返す。fail-soft。"""
        try:
            c = self._conn.cursor()
            cutoff = now_ts - ttl_sec
            res = c.execute("DELETE FROM agent_interest WHERE last_seen_ts < ? AND score < ?", (cutoff, min_score))
            self._conn.commit()
            return res.rowcount if hasattr(res, 'rowcount') else 0
        except Exception as e:
            logger = getattr(self, 'logger', None)
            if logger:
                logger.debug(f"cleanup_agent_interest failed: {e}")
            return 0
    def get_top_avatar_hashes_with_last_seen(self, speaker_key: str, limit: int = 3):
        """
        Returns [(avatar_hash, seen_count, last_seen_ts), ...] for the speaker, sorted by seen_count desc, last_seen_ts desc.
        """
        try:
            c = self._conn.cursor()
            rows = c.execute(
                """
                SELECT avatar_hash, seen_count, last_seen_ts FROM avatar_usage
                WHERE speaker_key=?
                ORDER BY seen_count DESC, last_seen_ts DESC
                LIMIT ?
                """,
                (speaker_key, limit)
            ).fetchall()
            return [(r[0], r[1], r[2]) for r in rows]
        except Exception as e:
            logger = getattr(self, 'logger', None)
            if logger:
                logger.debug(f"get_top_avatar_hashes_with_last_seen failed: {e}")
            return []

    def get_top_avatar_hashes_decayed(
        self,
        speaker_key: str,
        limit: int,
        now_ts: int,
        half_life_sec: float,
        floor_weight: float,
    ) -> list[tuple[str, float]]:
        """
        Returns [(avatar_hash, decayed_score), ...] for the speaker, sorted by -score, hash asc. Fail-soft ([] on error).
        """
        try:
            items = self.get_top_avatar_hashes_with_last_seen(speaker_key, 100)
            from core.memory_decay import apply_decay_to_counts
            decayed = apply_decay_to_counts(items, now_ts, half_life_sec, floor_weight)
            # 上位limitのみ返す
            return decayed[:limit]
        except Exception as e:
            logger = getattr(self, 'logger', None)
            if logger:
                logger.debug(f"get_top_avatar_hashes_decayed failed: {e}")
            return []

    def _read_style_profile_meta(self, speaker_key: str) -> Optional[tuple[int, int]]:
        """
        Returns (updated_ts, total_utt_count) or None
        """
        try:
            c = self._conn.cursor()
            row = c.execute("SELECT updated_ts, total_utt_count FROM speaker_style_profile WHERE speaker_key=?", (speaker_key,)).fetchone()
            if row:
                return int(row[0]), int(row[1])
            return None
        except Exception as e:
            logger = getattr(self, 'logger', None)
            if logger:
                logger.debug(f"_read_style_profile_meta failed: {e}")
            return None

    def get_style_profile_decayed(self, speaker_key: str, now_ts: int, half_life_sec: float, floor_weight: float, min_total_utt_to_apply: int = 8) -> Optional[dict]:
        """
        Returns a decayed copy of style profile (countsのみ減衰)。fail-soft。
        """
        import copy
        from core.memory_decay import decay_factor
        if not speaker_key:
            return None
        base = self.get_style_profile(speaker_key)
        if base is None:
            return None
        # total_utt_count, updated_ts
        total_utt_count = base.get("total_utt_count")
        updated_ts = base.get("updated_ts")
        if total_utt_count is None or updated_ts is None:
            meta = self._read_style_profile_meta(speaker_key)
            if meta:
                updated_ts, total_utt_count = meta
            else:
                # fail-soft: 生profile返す
                return copy.deepcopy(base)
        if total_utt_count < min_total_utt_to_apply:
            return copy.deepcopy(base)
        dt_sec = max(0, now_ts - updated_ts)
        f = decay_factor(dt_sec, half_life_sec, floor_weight)
        out = copy.deepcopy(base)
        # 減衰対象
        for k in ["top_tokens", "top_bigrams", "filler"]:
            if k in out:
                new_list = []
                for e in out[k]:
                    c = e.get("c", 0)
                    c_decayed = c * f
                    c_out = int(round(c_decayed))
                    if c_out > 0:
                        new_list.append({"t": e.get("t", ""), "c": c_out})
                # 決定的: c desc, t asc, 上位20
                new_list.sort(key=lambda x: (-x["c"], x["t"]))
                out[k] = new_list[:20]
        # metaはそのまま/punct等もそのまま
        out["_decay"] = {"factor": f, "dt_sec": dt_sec}
        return out

    def update_style_profile(self, speaker_key: str, features: dict, now_ts: int) -> None:
        import json
        if not speaker_key:
            return
        try:
            c = self._conn.cursor()
            row = c.execute("SELECT profile_json, total_utt_count FROM speaker_style_profile WHERE speaker_key=?", (speaker_key,)).fetchone()
            if row:
                old = json.loads(row[0])
                count = int(row[1])
            else:
                old = {}
                count = 0
            # マージ
            def merge_top(lst1, lst2, k=20):
                d = {}
                for e in lst1:
                    d[e["t"]] = d.get(e["t"], 0) + int(e["c"])
                for e in lst2:
                    d[e["t"]] = d.get(e["t"], 0) + int(e["c"])
                merged = sorted([{"t": t, "c": c} for t, c in d.items()], key=lambda x: -x["c"])[:k]
                return merged
            profile = {}
            for k in ["top_tokens", "top_bigrams", "filler"]:
                profile[k] = merge_top(old.get(k, []), features.get(k, []), 20)
            # punct/politeness/length: 加重平均
            def avg_merge(oldv, newv, keylist):
                res = {}
                for k in keylist:
                    ov = old.get(k, 0.0) if old else 0.0
                    nv = newv.get(k, 0.0) if newv else 0.0
                    res[k] = (ov * count + nv) / (count + 1)
                return res
            profile["punct"] = avg_merge(old.get("punct", {}), features.get("punct", {}), ["q_rate", "ex_rate", "emoji_rate"])
            profile["politeness"] = avg_merge(old.get("politeness", {}), features.get("politeness", {}), ["desu_masu", "da_dearu"])
            profile["length"] = avg_merge(old.get("length", {}), features.get("length", {}), ["avg_chars"])
            total_utt_count = count + 1
            c.execute("REPLACE INTO speaker_style_profile (speaker_key, updated_ts, total_utt_count, profile_json) VALUES (?, ?, ?, ?)",
                      (speaker_key, now_ts, total_utt_count, json.dumps(profile, ensure_ascii=False, sort_keys=True)))
            self._conn.commit()
        except Exception as e:
            logger = getattr(self, 'logger', None)
            if logger:
                logger.warning(f"update_style_profile failed: {e}")
            else:
                print(f"update_style_profile failed: {e}")

    def get_style_profile(self, speaker_key: str):
        import json
        if not speaker_key:
            return None
        try:
            c = self._conn.cursor()
            row = c.execute("SELECT profile_json FROM speaker_style_profile WHERE speaker_key=?", (speaker_key,)).fetchone()
            if row:
                return json.loads(row[0])
            return None
        except Exception as e:
            logger = getattr(self, 'logger', None)
            if logger:
                logger.debug(f"get_style_profile failed: {e}")
            return None


    def record_avatar_hash(self, speaker_key: str, avatar_hash: str, now_ts: int) -> None:
        try:
            c = self._conn.cursor()
            c.execute("""
                INSERT INTO avatar_usage (speaker_key, avatar_hash, first_seen_ts, last_seen_ts, seen_count)
                VALUES (?, ?, ?, ?, 1)
                ON CONFLICT(speaker_key, avatar_hash) DO UPDATE SET
                  last_seen_ts=excluded.last_seen_ts,
                  seen_count=avatar_usage.seen_count+1
            """, (speaker_key, avatar_hash, now_ts, now_ts))
            self._conn.commit()
        except Exception as e:
            logger = getattr(self, 'logger', None)
            if logger:
                logger.debug(f"record_avatar_hash failed: {e}")
            else:
                print(f"record_avatar_hash failed: {e}")

    def get_recent_avatar_hash(self, speaker_key: str) -> Optional[str]:
        try:
            c = self._conn.cursor()
            row = c.execute("""
                SELECT avatar_hash FROM avatar_usage
                WHERE speaker_key=?
                ORDER BY last_seen_ts DESC LIMIT 1
            """, (speaker_key,)).fetchone()
            if row:
                return row[0]
            return None
        except Exception as e:
            logger = getattr(self, 'logger', None)
            if logger:
                logger.debug(f"get_recent_avatar_hash failed: {e}")
            return None

    def get_top_avatar_hashes(self, speaker_key: str, limit: int=3):
        try:
            c = self._conn.cursor()
            rows = c.execute("""
                SELECT avatar_hash, seen_count FROM avatar_usage
                WHERE speaker_key=?
                ORDER BY seen_count DESC, last_seen_ts DESC
                LIMIT ?
            """, (speaker_key, limit)).fetchall()
            return [(r[0], r[1]) for r in rows]
        except Exception as e:
            logger = getattr(self, 'logger', None)
            if logger:
                logger.debug(f"get_top_avatar_hashes failed: {e}")
            return []
    def __init__(self, db_path: str = ":memory:"):
        # ensure directory exists for file paths
        if db_path != ":memory:":
            d = os.path.dirname(db_path)
            if d and not os.path.exists(d):
                os.makedirs(d, exist_ok=True)
        self.db_path = db_path
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

        # Avatar usage store (shares DB file)
        self.avatar_store = AvatarStore(db_path)
    # Avatar usage API
    def record_avatar_seen(self, speaker_key: str, avatar_id: str, avatar_name: Optional[str] = None):
        self.avatar_store.record_avatar_seen(speaker_key, avatar_id, avatar_name)

    def get_top_avatars(self, speaker_key: str, limit: int = 3) -> List[Dict]:
        return self.avatar_store.get_top_avatars(speaker_key, limit)

    def get_avatar_stats(self, speaker_key: str, avatar_id: str) -> Optional[Dict]:
        return self.avatar_store.get_avatar_stats(speaker_key, avatar_id)

    def _init_schema(self) -> None:
        c = self._conn.cursor()
        for s in SCHEMA:
            c.executescript(s)
        self._conn.commit()

    def _now_iso(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def get_profile_by_alias(self, alias: str) -> Optional[Dict]:
        c = self._conn.cursor()
        r = c.execute("SELECT speaker_key FROM speaker_alias WHERE alias = ?", (alias,)).fetchone()
        if not r:
            return None
        sk = r[0]
        row = c.execute("SELECT * FROM speaker_profiles WHERE speaker_key = ?", (sk,)).fetchone()
        if not row:
            return None
        return dict(row)

    def set_profile(self, alias: str, display_name: str, consent: bool = True) -> Dict:
        c = self._conn.cursor()
        now = self._now_iso()
        # speaker_key deterministic for simplicity
        speaker_key = f"spk:{alias}"
        existing = c.execute("SELECT * FROM speaker_profiles WHERE speaker_key = ?", (speaker_key,)).fetchone()
        if existing:
            c.execute("UPDATE speaker_profiles SET display_name = ?, updated_at = ?, consent = ? WHERE speaker_key = ?", (display_name, now, int(bool(consent)), speaker_key))
        else:
            c.execute("INSERT INTO speaker_profiles (speaker_key, display_name, created_at, updated_at, consent) VALUES (?, ?, ?, ?, ?)", (speaker_key, display_name, now, now, int(bool(consent))))
        # upsert alias
        c.execute("INSERT OR REPLACE INTO speaker_alias (alias, speaker_key) VALUES (?, ?)", (alias, speaker_key))
        self._conn.commit()
        return self.get_profile_by_alias(alias)

    def forget_profile(self, alias: str) -> bool:
        c = self._conn.cursor()
        r = c.execute("SELECT speaker_key FROM speaker_alias WHERE alias = ?", (alias,)).fetchone()
        if not r:
            return False
        sk = r[0]
        # delete alias mapping and profile
        c.execute("DELETE FROM speaker_alias WHERE alias = ?", (alias,))
        c.execute("DELETE FROM speaker_profiles WHERE speaker_key = ?", (sk,))
        self._conn.commit()
        return True

    def forget_by_name(self, display_name: str) -> int:
        c = self._conn.cursor()
        rows = c.execute("SELECT speaker_key FROM speaker_profiles WHERE display_name = ?", (display_name,)).fetchall()
        count = 0
        for r in rows:
            sk = r[0]
            c.execute("DELETE FROM speaker_alias WHERE speaker_key = ?", (sk,))
            c.execute("DELETE FROM speaker_profiles WHERE speaker_key = ?", (sk,))
            count += 1
        self._conn.commit()
        return count

    def touch_seen(self, alias: str) -> bool:
        c = self._conn.cursor()
        r = c.execute("SELECT speaker_key FROM speaker_alias WHERE alias = ?", (alias,)).fetchone()
        if not r:
            return False
        sk = r[0]
        now = self._now_iso()
        c.execute("UPDATE speaker_profiles SET last_seen_at = ? WHERE speaker_key = ?", (now, sk))
        self._conn.commit()
        return True

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass
