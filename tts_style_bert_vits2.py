from dataclasses import dataclass
from typing import Optional
import threading
import hashlib

# --- Prosody and SpeakResult ---
@dataclass(frozen=True)
class Prosody:
    speaking_rate: float
    pitch_shift: float
    energy: float

@dataclass(frozen=True)
class SpeakResult:
    ok: bool
    chunk_id: str
    duration_sec: float
    error: Optional[str] = None

# --- Deterministic prosody mapping ---
def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def prosody_from_scalars(s):
    speaking_rate = clamp(1.0 + 0.25 * s.arousal, 0.85, 1.20)
    pitch_shift   = clamp(0.15 * s.valence, -0.20, 0.20)
    energy        = clamp(1.0 + 0.30 * s.interest, 0.90, 1.25)
    return Prosody(
        float(f"{speaking_rate:.4f}"),
        float(f"{pitch_shift:.4f}"),
        float(f"{energy:.4f}")
    )

# --- LocalTTS fail-soft adapter ---
class LocalTTS:
    def __init__(self, cfg, clock, rng, logger, audio_out=None):
        self.cfg = cfg
        self.clock = clock
        self.rng = rng
        self.logger = logger
        self.audio_out = audio_out
        self._engine = None
        self._engine_error_logged = False
        self._prefetch_cache = {}  # chunk_id -> wav_bytes
        self._cache_lock = threading.Lock()
        self._stop_requested = False
        try:
            # Try import here; fail-soft
            import style_bert_vits2
            self._engine = style_bert_vits2
        except Exception as e:
            self._engine = None
            if not self._engine_error_logged:
                self.logger.warning("Style-BERT-VITS2 unavailable: %s", e)
                self._engine_error_logged = True
    def is_available(self):
        return self._engine is not None and self.cfg.get('tts.enabled', False)
    def prefetch(self, text: str, prosody: Prosody, *, chunk_id: str):
        if not self.is_available():
            return
        try:
            key = (chunk_id, prosody.speaking_rate, prosody.pitch_shift, prosody.energy)
            wav_bytes = self._synthesize(text, prosody)
            with self._cache_lock:
                self._prefetch_cache[key] = wav_bytes
                # Keep cache small
                if len(self._prefetch_cache) > 2:
                    self._prefetch_cache.pop(next(iter(self._prefetch_cache)))
        except Exception as e:
            self.logger.debug(f"TTS prefetch failed: {e}")
    def speak(self, text: str, prosody: Prosody, *, chunk_id: str) -> SpeakResult:
        if not self.is_available():
            return SpeakResult(False, chunk_id, 0.0, error="TTS unavailable")
        key = (chunk_id, prosody.speaking_rate, prosody.pitch_shift, prosody.energy)
        try:
            with self._cache_lock:
                wav_bytes = self._prefetch_cache.pop(key, None)
            if wav_bytes is None:
                wav_bytes = self._synthesize(text, prosody)
            if self._stop_requested:
                return SpeakResult(False, chunk_id, 0.0, error="TTS stopped")
            duration_sec = self._play_wav(wav_bytes)
            return SpeakResult(True, chunk_id, duration_sec)
        except Exception as e:
            self.logger.warning(f"TTS speak failed: {e}")
            return SpeakResult(False, chunk_id, 0.0, error=str(e))
    def stop(self):
        self._stop_requested = True
        # If audio_out supports stop, call it
        if hasattr(self.audio_out, 'stop'):
            try:
                self.audio_out.stop()
            except Exception:
                pass
    def _synthesize(self, text, prosody):
        # Minimal stub: replace with actual engine call
        if not self._engine:
            raise RuntimeError("TTS engine unavailable")
        # Example: wav_bytes = self._engine.synthesize(text, prosody)
        # For now, return dummy bytes
        return b''
    def _play_wav(self, wav_bytes):
        # Use provided audio_out if available
        if self.audio_out and hasattr(self.audio_out, 'play_bytes'):
            try:
                ok = self.audio_out.play_bytes(wav_bytes)
                return 0.0 if not ok else 1.0  # Duration unknown
            except Exception:
                return 0.0
        # No audio output available
        return 0.0
