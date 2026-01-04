import math

class EmotionAfterglow:
    def __init__(self, time_provider, config, clamp_fn):
        self.tp = time_provider
        self.cfg = config
        self.clamp = clamp_fn
        self.enabled = bool(config.get('enable_emotion_afterglow', False))
        self.tau = max(float(config.get('afterglow_tau_sec', 18.0)), 5.0)
        self.tick_hz = min(max(float(config.get('afterglow_tick_hz', 0.5)), 0.1), 1.0)
        self.min_delta = float(config.get('afterglow_min_delta', 0.002))
        self.max_hold = min(float(config.get('afterglow_max_hold_sec', 60.0)), 120.0)
        self.active = False
        self.start_time = 0.0
        self.last_tick_time = 0.0
        self.hold_valence = 0.0
        self.hold_interest = 0.0
        self.disable = False
    def on_emit_end(self, valence, interest):
        if not self.enabled or self.disable:
            return
        now = self.tp.now()
        self.active = True
        self.start_time = now
        self.last_tick_time = now
        self.hold_valence = float(valence)
        self.hold_interest = float(interest)
    def tick(self, baseline_valence, baseline_interest, state=None):
        if not self.enabled or self.disable or state in ("ALERT", "SEARCH"):
            self.active = False
            return baseline_valence, baseline_interest
        if not self.active:
            return baseline_valence, baseline_interest
        try:
            now = self.tp.now()
            dt = now - self.last_tick_time
            self.last_tick_time = now
            alpha = 1.0 - math.exp(-dt / self.tau)
            v = self.hold_valence * (1 - alpha) + baseline_valence * alpha
            i = self.hold_interest * (1 - alpha) + baseline_interest * alpha
            # Clamp
            v = self.clamp(v, -1.0, 1.0)
            i = self.clamp(i, 0.0, 1.0)
            # Stop conditions
            if (abs(v - baseline_valence) < self.min_delta or
                abs(i - baseline_interest) < self.min_delta or
                now - self.start_time > self.max_hold):
                self.active = False
                return baseline_valence, baseline_interest
            return v, i
        except Exception:
            self.disable = True
            self.active = False
            return baseline_valence, baseline_interest
