import math
from core.determinism import DeterministicRNG, TimeProvider

def clamp(x, lo, hi):
    try:
        return max(lo, min(hi, float(x)))
    except Exception:
        return lo

def compute_idle_drift(now, seed, amp, period):
    # Deterministic phase offsets
    rng = DeterministicRNG(seed)
    phase_valence = rng.uniform(0, math.pi)
    phase_interest = rng.uniform(0, math.pi)
    # Drift math
    valence = amp * math.sin(2 * math.pi * now / period + phase_valence)
    interest = amp * 0.8 * math.sin(2 * math.pi * now / period + phase_interest)
    return {
        'valence': clamp(valence, -amp, amp),
        'interest': clamp(interest, -amp*0.8, amp*0.8)
    }

import hashlib

def phase_from_seed(seed, label):
    h = hashlib.sha256(f"{seed}:{label}".encode()).digest()
    x = int.from_bytes(h[:8], 'big')
    return (x / 2**64) * 2 * math.pi

class IdleFaceDrift:
    def __init__(self, osc_sender, time_provider, config, clamp_fn, state_getter, speaking_getter):
        self.osc = osc_sender
        self.tp = time_provider
        self.cfg = config
        self.clamp = clamp_fn
        self.state_getter = state_getter
        self.speaking_getter = speaking_getter
        self.enabled = bool(config.get('enable_idle_face_drift', False))
        self.amp = clamp_fn(float(config.get('idle_face_drift_amp', 0.04)), 0.0, 0.05)
        self.period = max(float(config.get('idle_face_drift_period_sec', 50.0)), 40.0)
        self.tick_hz = clamp_fn(float(config.get('idle_face_drift_tick_hz', 0.2)), 0.05, 1.0)
        self.seed = int(config.get('presence_seed', 1337))
        self.phase_v = phase_from_seed(self.seed, "valence")
        self.phase_i = phase_from_seed(self.seed, "interest")
        self.next_due = 0.0
    def tick(self):
        if not self.enabled:
            return
        if self.state_getter() != "IDLE":
            return
        if self.speaking_getter():
            return
        now = self.tp.now()
        if now < self.next_due:
            return
        self.next_due = now + 1.0 / self.tick_hz
        t = now
        dv = self.amp * math.sin(2 * math.pi * t / self.period + self.phase_v)
        di = self.amp * 0.8 * math.sin(2 * math.pi * t / self.period + self.phase_i)
        # Baselines: prefer context/state, else neutral
        valence_base = 0.0
        interest_base = 0.5
        valence = self.clamp(valence_base + dv, -1.0, 1.0)
        interest = self.clamp(interest_base + di, 0.0, 1.0)
        try:
            self.osc.send('/avatar/parameters/face_valence', valence)
            self.osc.send('/avatar/parameters/face_interest', interest)
        except Exception:
            return
        self.last_tick = now
        drift = compute_idle_drift(now, self.seed, self.amp, self.period)
        try:
            self.osc.send_param('face_valence', drift['valence'])
            self.osc.send_param('face_interest', drift['interest'])
        except Exception:
            pass
