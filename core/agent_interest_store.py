from typing import Optional
from core.memory_decay import decay_factor
import sqlite3

class AgentInterestStore:
    def __init__(self, speaker_store_or_conn, logger=None):
        self.logger = logger
        self.disabled = False
        try:
            if hasattr(speaker_store_or_conn, '_conn'):
                self._conn = speaker_store_or_conn._conn
            else:
                self._conn = speaker_store_or_conn
        except Exception as e:
            if self.logger:
                self.logger.warning(f"AgentInterestStore init failed: {e}")
            self.disabled = True

    def bump_interest(self, topic: str, now_ts: int, amount: float = 1.0) -> None:
        if self.disabled or not topic or amount <= 0:
            return
        try:
            c = self._conn.cursor()
            row = c.execute("SELECT score, last_seen_ts FROM agent_interest WHERE topic=?", (topic,)).fetchone()
            retention = 0.98
            if row:
                score, last_seen_ts = float(row[0]), int(row[1])
                score = score * retention + amount
                c.execute("UPDATE agent_interest SET score=?, last_seen_ts=? WHERE topic=?", (score, now_ts, topic))
            else:
                c.execute("INSERT INTO agent_interest (topic, last_seen_ts, score) VALUES (?, ?, ?)", (topic, now_ts, amount))
            self._conn.commit()
        except Exception as e:
            if self.logger:
                self.logger.warning(f"bump_interest failed: {e}")
            self.disabled = True

    def get_interest_weights_decayed(
        self,
        now_ts: int,
        base_weights: dict,
        half_life_sec: float,
        floor_weight: float,
        max_boost: float = 0.6,
        clamp_min_mul: float = 0.5,
        clamp_max_mul: float = 2.0,
    ) -> dict:
        if self.disabled:
            return dict(base_weights)
        try:
            out = dict(base_weights)
            c = self._conn.cursor()
            rows = c.execute("SELECT topic, score, last_seen_ts FROM agent_interest").fetchall()
            for topic, score, last_seen_ts in rows:
                if topic not in base_weights:
                    continue
                dt = max(0, now_ts - int(last_seen_ts))
                f = decay_factor(dt, half_life_sec, floor_weight)
                decayed = float(score) * f
                norm = decayed / (decayed + 3.0) if decayed > 0 else 0.0
                boost = max_boost * norm
                base = base_weights[topic]
                val = base + boost
                val = max(base * clamp_min_mul, min(val, base * clamp_max_mul))
                out[topic] = val
            return out
        except Exception as e:
            if self.logger:
                self.logger.warning(f"get_interest_weights_decayed failed: {e}")
            self.disabled = True
            return dict(base_weights)
