import random
import time

THOUGHT_TOKENS = ["...", "えっと", "んー"]

class ThoughtLeakage:
    def __init__(self):
        self.last_emit_ts = 0.0
        self.cooldown = 90.0
        self.enabled = False
    def maybe_emit(self, curiosity, interest, state, now_ts=None):
        """
        Returns a single non-verbal token if eligible, else None.
        Only triggers in IDLE, cooldown >= 90s, scalar gated by curiosity+interest.
        Deterministic, fail-soft.
        """
        if not self.enabled:
            return None
        if state != "IDLE":
            return None
        now = now_ts if now_ts is not None else time.time()
        if now - self.last_emit_ts < self.cooldown:
            return None
        # Scalar gate: curiosity+interest > 0.5
        try:
            scalar = float(curiosity) + float(interest)
            if scalar < 0.5:
                return None
            # Deterministic token selection
            idx = int((scalar * 1000 + int(now // 10)) % len(THOUGHT_TOKENS))
            token = THOUGHT_TOKENS[idx]
            self.last_emit_ts = now
            return token
        except Exception:
            return None
