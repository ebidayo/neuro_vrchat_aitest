def clamp(x, lo, hi):
    try:
        return max(lo, min(hi, float(x)))
    except Exception:
        return lo

def map_prosody(valence, interest, arousal, config=None):
    """
    Map valence/interest/arousal to prosody dict for TTS.
    config: dict with optional keys pitch_gain, speed_gain, energy_gain
    Returns: dict(pitch, speed, energy)
    """
    cfg = (config or {}).get('audio', {}).get('prosody', {}) if config else {}
    pitch_gain = clamp(cfg.get('pitch_gain', 0.15), 0.05, 0.3)
    speed_gain = clamp(cfg.get('speed_gain', 0.20), 0.05, 0.4)
    energy_gain = clamp(cfg.get('energy_gain', 0.30), 0.1, 0.5)
    pitch = clamp(1.0 + valence * pitch_gain + interest * 0.10, 0.7, 1.3)
    speed = clamp(1.0 + arousal * speed_gain, 0.7, 1.5)
    energy = clamp(0.8 + interest * energy_gain, 0.5, 1.5)
    return {'pitch': pitch, 'speed': speed, 'energy': energy}
