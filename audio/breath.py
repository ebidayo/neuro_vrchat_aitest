import random
import time
import logging

def maybe_play_breath(arousal, confidence, state, after_wav=True, enabled=False):
    """
    Play a micro-breath sound after speech if conditions met.
    Only triggers if enabled, after_wav, not in ALERT/SEARCH/name-learning.
    Probability capped at 0.15, arousal > 0.35, confidence > 0.4.
    Fail-soft: never raises, silent on error.
    """
    if not enabled:
        return
    if not after_wav:
        return
    if state in ("ALERT", "SEARCH", "NAME_LEARNING"):
        return
    try:
        if arousal > 0.35 and confidence > 0.4:
            # Deterministic probability: hash of time+arousal+confidence
            seed = int(arousal * 1000 + confidence * 1000 + int(time.time() // 2))
            rng = random.Random(seed)
            if rng.random() < 0.15:
                # Play breath sound (placeholder: log only)
                logging.debug("[Breath] Played micro-breath sound.")
                # Actual audio playback would go here
    except Exception as e:
        logging.debug(f"[Breath] fail-soft: {e}")
