import sqlite3
from typing import Optional, List, Dict
import threading
import time

class AvatarStore:
    def __init__(self, db_path: str = ":memory:"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.lock = threading.Lock()
        self._init_tables()

    def _init_tables(self):
        with self.conn:
            self.conn.execute("""
            CREATE TABLE IF NOT EXISTS avatar_usage (
                speaker_key TEXT,
                avatar_id TEXT,
                avatar_name TEXT,
                first_seen_at TEXT,
                last_seen_at TEXT,
                seen_count INTEGER,
                PRIMARY KEY (speaker_key, avatar_id)
            )
            """)

    def record_avatar_seen(self, speaker_key: str, avatar_id: str, avatar_name: Optional[str] = None):
        now = time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime())
        with self.lock, self.conn:
            cur = self.conn.execute("""
                SELECT seen_count FROM avatar_usage WHERE speaker_key=? AND avatar_id=?
            """, (speaker_key, avatar_id))
            row = cur.fetchone()
            if row:
                self.conn.execute("""
                    UPDATE avatar_usage SET last_seen_at=?, seen_count=seen_count+1, avatar_name=COALESCE(?, avatar_name)
                    WHERE speaker_key=? AND avatar_id=?
                """, (now, avatar_name, speaker_key, avatar_id))
            else:
                self.conn.execute("""
                    INSERT INTO avatar_usage (speaker_key, avatar_id, avatar_name, first_seen_at, last_seen_at, seen_count)
                    VALUES (?, ?, ?, ?, ?, 1)
                """, (speaker_key, avatar_id, avatar_name, now, now))

    def get_top_avatars(self, speaker_key: str, limit: int = 3) -> List[Dict]:
        cur = self.conn.execute("""
            SELECT avatar_id, avatar_name, seen_count, last_seen_at FROM avatar_usage
            WHERE speaker_key=?
            ORDER BY seen_count DESC, last_seen_at DESC
            LIMIT ?
        """, (speaker_key, limit))
        return [dict(row) for row in map(lambda x: {
            'avatar_id': x[0], 'avatar_name': x[1], 'seen_count': x[2], 'last_seen_at': x[3]
        }, cur.fetchall())]

    def get_avatar_stats(self, speaker_key: str, avatar_id: str) -> Optional[Dict]:
        cur = self.conn.execute("""
            SELECT avatar_id, avatar_name, seen_count, first_seen_at, last_seen_at FROM avatar_usage
            WHERE speaker_key=? AND avatar_id=?
        """, (speaker_key, avatar_id))
        row = cur.fetchone()
        if row:
            return {
                'avatar_id': row[0],
                'avatar_name': row[1],
                'seen_count': row[2],
                'first_seen_at': row[3],
                'last_seen_at': row[4]
            }
        return None
