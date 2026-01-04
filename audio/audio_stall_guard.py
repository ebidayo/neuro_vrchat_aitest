import time
import logging

def detect_audio_stall(start_ts, end_ts, wav_played, timeout=2.5, glitch_scalar=0.0):
    """
    Detects audio stall (WAV play failed or took too long).
    If detected, returns increased glitch_scalar (capped), logs event.
    Never emits speech.
    """
    try:
        if not wav_played or (end_ts - start_ts) > timeout:
            logging.warning("[AudioStall] Detected audio stall.")
            return min(glitch_scalar + 0.05, 1.0)
    except Exception as e:
        logging.debug(f"[AudioStall] fail-soft: {e}")
    return glitch_scalar
