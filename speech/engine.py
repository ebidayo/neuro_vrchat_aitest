from .types import VoiceSpec, Prosody, SpeechMeta, SpeechItem
from .interfaces import TTSProvider, AudioSink
from .queue import SpeechQueue
from typing import Optional


import time
from .wav_util import try_get_wav_duration_ms

class SpeechEngine:
    def __init__(self, tts: TTSProvider, sink: AudioSink, queue: SpeechQueue):
        self.tts = tts
        self.sink = sink
        self.queue = queue
        self._speaking_until_ms = 0  # deterministic suppression window (epoch ms)

    def is_speaking(self, now_ms: Optional[int] = None) -> bool:
        """Returns True if currently in the self-voice suppression window (deterministic, ms)."""
        n = now_ms if now_ms is not None else int(time.time() * 1000)
        return n < self._speaking_until_ms

    def submit_text(self, text: str, *, voice: Optional[VoiceSpec] = None, prosody: Optional[Prosody] = None, meta: Optional[SpeechMeta] = None, now_ms: Optional[int] = None) -> None:
        try:
            v = voice if voice is not None else VoiceSpec()
            p = prosody if prosody is not None else {}
            m = meta if meta is not None else SpeechMeta()
            n = now_ms if now_ms is not None else 0
            self.queue.submit_text(text, v, p, m, n)
        except Exception:
            pass

    def tick(self, now_ms: int) -> None:
        try:
            item = self.queue.pop_next(now_ms)
            if not item:
                return
            try:
                audio = self.tts.synthesize(
                    item.text,
                    item.voice,
                    item.prosody,
                    seed=item.meta.seed,
                    request_id=item.meta.request_id
                )
            except Exception:
                audio = None
            duration_ms = None
            if audio:
                # Try to get duration from TTSAudio, else fallback to wav_util
                duration_ms = getattr(audio, "duration_ms", None)
                if duration_ms is None and getattr(audio, "format", None) == "wav":
                    try:
                        duration_ms = try_get_wav_duration_ms(getattr(audio, "pcm_bytes", b""))
                    except Exception:
                        duration_ms = None
                # Fallback: 1200ms if unknown
                if not duration_ms:
                    duration_ms = 1200
                self._speaking_until_ms = max(self._speaking_until_ms, now_ms + int(duration_ms))
                self.sink.play(audio)
        except Exception:
            pass

    def flush(self, reason: str) -> None:
        try:
            self.queue.clear(reason)
        except Exception:
            pass
