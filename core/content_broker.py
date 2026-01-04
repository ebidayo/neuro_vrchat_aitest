import time
from collections import deque
from threading import Lock
import hashlib

class TTLSet:
    def __init__(self, ttl_sec):
        self.ttl_sec = ttl_sec
        self.data = {}
        self.lock = Lock()
    def add(self, key, now):
        with self.lock:
            self.data[key] = now + self.ttl_sec
    def __contains__(self, key):
        now = time.time()
        with self.lock:
            exp = self.data.get(key)
            if exp is None:
                return False
            if exp < now:
                del self.data[key]
                return False
            return True
    def cleanup(self):
        now = time.time()
        with self.lock:
            for k in list(self.data):
                if self.data[k] < now:
                    del self.data[k]

class ContentBroker:
    def __init__(self, config, interest_store=None, logger=None):
        self.cfg = config["content_broker"]
        self.pending = deque()
        self.idle_pending = deque()
        self.used_ids = TTLSet(self.cfg["used_ttl_sec"])
        self.last_emit_ts = 0.0
        self.session_emitted_count = 0
        self.last_talk_end_ts = 0.0
        self.idle_last_emit_ts = 0.0
        self.idle_session_emitted_count = 0
        self.lock = Lock()
        self.interest_store = interest_store
        self.logger = logger
    def add_items(self, items, now_ts=None):
        import time
        try:
            if now_ts is None:
                now_ts = int(time.time())
            base_weights = self.cfg["interest"]["weights"]
            weights = base_weights
            if (
                self.interest_store is not None
                and self.cfg["interest"].get("enabled", True)
            ):
                try:
                    # memory_decay設定はcfgの上位で判定する想定（mainで注入時に保証）
                    weights = self.interest_store.get_interest_weights_decayed(
                        now_ts=now_ts,
                        base_weights=base_weights,
                        half_life_sec=self.cfg["interest"].get("half_life_days", 7)*86400,
                        floor_weight=self.cfg["interest"].get("floor_weight", 0.1),
                    )
                except Exception as e:
                    if self.logger:
                        self.logger.debug(f"interest_store.get_interest_weights_decayed failed: {e}")
                    weights = base_weights
            scored = []
            idle_scored = []
            for item in items:
                topic = item.get("topic", self.cfg["interest"].get("unknown_topic", "other"))
                base_score = 0.6 if item.get("kind") == "news" else 0.5
                iw = weights.get(topic, weights.get(self.cfg["interest"].get("unknown_topic", "other"), 1.0))
                score = base_score * iw
                if score < self.cfg["interest"]["drop_threshold"]:
                    continue
                if item["id"] in self.used_ids:
                    continue
                scored.append((score, -item["published_ts"], item["id"], item))
                # idle_asideは閾値緩め
                idle_score = max(score, self.cfg["idle_aside"]["min_confidence"])
                idle_scored.append((idle_score, -item["published_ts"], item["id"], item))
            scored.sort(reverse=True)
            idle_scored.sort(reverse=True)
            with self.lock:
                for _,_,_,item in scored[:self.cfg["max_pending"]]:
                    self.pending.append(item)
                for _,_,_,item in idle_scored[:self.cfg["max_idle_pending"]]:
                    self.idle_pending.append(item)
        except Exception as e:
            if self.logger:
                self.logger.debug(f"add_items failed: {e}")
    def notify_talk_end(self, now):
        with self.lock:
            self.last_talk_end_ts = now
    def should_emit(self, now, scalars, state):
        if not self.cfg["enabled"]:
            return False
        if now - self.last_emit_ts < self.cfg["emit_cooldown_sec"]:
            return False
        if self.session_emitted_count >= self.cfg["session_max_emits"]:
            return False
        if now - self.last_talk_end_ts < self.cfg["talk_cooldown_after_end_sec"]:
            return False
        if scalars.get("confidence",1.0) < self.cfg["min_confidence"]:
            return False
        if scalars.get("social_pressure",0.0) > self.cfg["max_social_pressure"]:
            return False
        if scalars.get("arousal",0.0) > self.cfg["max_arousal"]:
            return False
        if self.cfg["require_idle_state"] and state != "IDLE":
            return False
        # ALERT/SEARCH/name-learning gatingは外部で
        return True
    def pop_for_conversation(self, now_ts=None, scalars=None, state=None):
        import time
        if now_ts is None:
            now_ts = int(time.time())
        with self.lock:
            while self.pending:
                item = self.pending.popleft()
                if item["id"] in self.used_ids:
                    continue
                self.used_ids.add(item["id"], now_ts)
                self.last_emit_ts = now_ts
                self.session_emitted_count += 1
                # emit直後にinterest bump（fail-soft）
                if self.interest_store:
                    try:
                        topic = item.get("topic") or self.cfg["interest"].get("unknown_topic", "other")
                        self.interest_store.bump_interest(topic, now_ts=now_ts, amount=1.0)
                    except Exception as e:
                        if self.logger:
                            self.logger.debug(f"bump_interest failed: {e}")
                return item
        return None
    def pop_for_idle_aside(self, now_ts=None, scalars=None, state=None):
        import time
        if now_ts is None:
            now_ts = int(time.time())
        if not self.cfg["idle_aside"]["enabled"]:
            return None
        with self.lock:
            if self.idle_session_emitted_count >= self.cfg["idle_aside"]["session_max_emits"]:
                return None
            if now_ts - self.idle_last_emit_ts < self.cfg["idle_aside"]["emit_cooldown_sec"]:
                return None
            while self.idle_pending:
                item = self.idle_pending.popleft()
                if item["id"] in self.used_ids:
                    continue
                self.used_ids.add(item["id"], now_ts)
                self.idle_last_emit_ts = now_ts
                self.idle_session_emitted_count += 1
                return item
        return None
