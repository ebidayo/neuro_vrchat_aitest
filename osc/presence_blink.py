from core.determinism import DeterministicRNG, TimeProvider

class PresenceBlink:
    def __init__(self, osc_sender, config, time_provider=None):
        self.osc = osc_sender
        self.cfg = config
        self.tp = time_provider or TimeProvider()
        self.enabled = bool(config.get('enable_blink_hint', False))
        self.min_sec = max(1.0, float(config.get('blink_min_sec', 3.0)))
        self.max_sec = max(self.min_sec, float(config.get('blink_max_sec', 8.0)))
        self.pulse_ms = int(config.get('blink_pulse_ms', 120))
        self.seed = int(config.get('presence_seed', 1337))
        self.last_blink = 0.0
        self.next_blink_due = 0.0
        self.is_pulsing = False
    def tick(self, state, is_speaking):
        if not self.enabled or state != 'IDLE' or is_speaking:
            return
        now = self.tp.now()
        rng = DeterministicRNG(self.seed + 12345)
        # Schedule next blink deterministically
        if self.next_blink_due == 0.0 or now >= self.next_blink_due:
            interval = rng.uniform(self.min_sec, self.max_sec)
            self.next_blink_due = now + interval
            self.is_pulsing = True
            try:
                self.osc.send_param('blink_hint', 1)
            except Exception:
                pass
        # End pulse after pulse_ms
        if self.is_pulsing and now - (self.next_blink_due - interval) >= self.pulse_ms / 1000.0:
            self.is_pulsing = False
            try:
                self.osc.send_param('blink_hint', 0)
            except Exception:
                pass
