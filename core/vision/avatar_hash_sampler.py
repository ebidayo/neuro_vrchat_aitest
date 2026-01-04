import threading
import logging
from typing import Optional, Callable
import time

class AvatarHashSampler:
    def __init__(self, get_roi_image_callable: Callable[[], 'Image.Image'], interval_sec: float, ttl_sec: float, cooldown_on_error_sec: float, logger=None):
        self.get_roi_image_callable = get_roi_image_callable
        self.interval_sec = interval_sec
        self.ttl_sec = ttl_sec
        self.cooldown_on_error_sec = cooldown_on_error_sec
        self.logger = logger or logging.getLogger(__name__)
        self._lock = threading.Lock()
        self._last_hash = None
        self._last_hash_ts = 0.0
        self._next_sample_ts = 0.0
        self._cooldown_until = 0.0

    def tick(self, now_monotonic: float) -> Optional[str]:
        with self._lock:
            # Helper to check TTL strictly
            def valid_hash():
                if self._last_hash and (now_monotonic - self._last_hash_ts) <= self.ttl_sec:
                    return self._last_hash
                return None

            # Cooldown on error
            if now_monotonic < self._cooldown_until:
                return valid_hash()
            # Interval check
            if now_monotonic < self._next_sample_ts:
                return valid_hash()
            try:
                img = self.get_roi_image_callable()
                if img is None:
                    raise RuntimeError("No ROI image available")
                from core.vision.avatar_hash import compute_avatar_phash
                h = compute_avatar_phash(img)
                if h:
                    self._last_hash = h
                    self._last_hash_ts = now_monotonic
                    self._next_sample_ts = now_monotonic + self.interval_sec
                    self.logger.info(f"avatar_hash updated {h[:8]}")
                    return h
                else:
                    self.logger.debug("avatar_hash: compute_avatar_phash returned None")
                    self._next_sample_ts = now_monotonic + self.interval_sec
            except Exception as e:
                self.logger.debug(f"avatar_hash sampling failed: {e}")
                self._cooldown_until = now_monotonic + self.cooldown_on_error_sec
            # After sampling or error, check TTL strictly
            return valid_hash()

    def _get_valid_hash(self, now_monotonic: float) -> Optional[str]:
        if self._last_hash and (now_monotonic - self._last_hash_ts) <= self.ttl_sec:
            return self._last_hash
        return None
