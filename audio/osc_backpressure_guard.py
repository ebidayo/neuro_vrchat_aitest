import time
import logging

def osc_backpressure_guard(latency_ms, update_freq, min_freq=0.5, max_freq=5.0):
    """
    If OSC send latency spikes, reduce face update frequency.
    Recovers gradually. No speech emitted.
    Returns new update_freq.
    """
    try:
        if latency_ms > 120:
            update_freq = max(min_freq, update_freq * 0.7)
            logging.warning(f"[OSCBackpressure] Latency {latency_ms}ms, reducing freq to {update_freq}")
        elif latency_ms < 60:
            update_freq = min(max_freq, update_freq * 1.05)
        return update_freq
    except Exception as e:
        logging.debug(f"[OSCBackpressure] fail-soft: {e}")
        return update_freq
