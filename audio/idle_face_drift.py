import math
import time

def compute_idle_face_drift(now_ts=None, seed=42, enabled=False):
    """
    Returns deterministic valence/interest drift for OSC idle face.
    Amplitude <= 0.05, period >= 40s, only if enabled.
    """
    if not enabled:
        return {'valence': 0.0, 'interest': 0.0}
    now = now_ts if now_ts is not None else time.time()
    # Deterministic slow drift
    period = 40.0
    amp = 0.05
    valence = amp * math.sin((now + seed) / period)
    interest = amp * math.cos((now + seed) / (period * 1.1))
    return {'valence': valence, 'interest': interest}
