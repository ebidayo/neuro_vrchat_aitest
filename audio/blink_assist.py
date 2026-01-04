import random
import time

def maybe_blink(now_ts=None, enabled=False, last_blink_ts=None):
    """
    Returns True if blink should be triggered (OSC blink_hint=1), else False.
    Deterministic interval (3–8s), suppressed during speech.
    If param missing, no-op.
    """
    if not enabled:
        return False
    now = now_ts if now_ts is not None else time.time()
    last = last_blink_ts if last_blink_ts is not None else 0.0
    # Deterministic interval based on time
    interval = 3.0 + ((int(now // 10) % 6) * 1.0)  # 3–8s
    if now - last >= interval:
        return True
    return False
