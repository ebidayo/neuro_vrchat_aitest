def compute_speaker_tempo(speaker_key, speaker_store, now_ts, config=None):
    """
    Returns dict:
      {
        'response_delay_ms': int,   # 0–800
        'idle_interval_scale': float,  # 0.7–1.2
        'prosody_speed_scale': float,  # 0.7–1.2
      }
    Fail-soft: if speaker_key is None or error, returns default.
    """
    # Defaults
    default = {'response_delay_ms': 0, 'idle_interval_scale': 1.0, 'prosody_speed_scale': 1.0}
    try:
        if not speaker_key or not speaker_store:
            return default
        # Recent activity: 0.0 (inactive) to 1.0 (very active)
        rec = 0.0
        try:
            rec = float(speaker_store.get_recency(speaker_key, now_ts))
        except Exception:
            rec = 0.0
        # avatar usage: 0.0–1.0
        usage = 0.0
        try:
            usage = float(speaker_store.get_avatar_usage(speaker_key, now_ts))
        except Exception:
            usage = 0.0
        # interest: 0.0–1.0
        interest = 0.0
        try:
            interest = float(speaker_store.get_interest(speaker_key, now_ts))
        except Exception:
            interest = 0.0
        # Combine: more active/engaged = faster
        act = min(1.0, max(0.0, 0.5*rec + 0.3*usage + 0.2*interest))
        # Delay: inverse to activity
        delay = int((1.0 - act) * 800)
        # Idle interval: more active = less idle
        idle_scale = 1.2 - 0.5*act
        # Prosody speed: more active = faster
        speed_scale = 0.7 + 0.5*act
        # Clamp
        delay = max(0, min(800, delay))
        idle_scale = max(0.7, min(1.2, idle_scale))
        speed_scale = max(0.7, min(1.2, speed_scale))
        return {
            'response_delay_ms': delay,
            'idle_interval_scale': idle_scale,
            'prosody_speed_scale': speed_scale
        }
    except Exception:
        return default
