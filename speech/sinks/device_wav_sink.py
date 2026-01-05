import threading
import queue
import wave
from typing import Optional
from ..types import TTSAudio
from ..interfaces import AudioSink, NullAudioSink

def create_device_wav_sink(name_contains: str, *, enabled: bool = True) -> AudioSink:
    try:
        import sounddevice as sd
        import numpy as np
    except ImportError:
        return NullAudioSink()
    if not enabled:
        return NullAudioSink()
    return DeviceWavSink(name_contains)

class DeviceWavSink(AudioSink):
    def __init__(self, name_contains: str, sample_rate_fallback: int = 48000, queue_max: int = 8):
        self.name_contains = name_contains
        self.sample_rate_fallback = sample_rate_fallback
        self._queue = queue.Queue(maxsize=queue_max)
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._stop = threading.Event()
        self._thread.start()

    def play(self, audio: TTSAudio) -> bool:
        if not audio or getattr(audio, "format", None) != "wav" or not getattr(audio, "pcm_bytes", None):
            return False
        try:
            # Drop oldest if full (deterministic)
            if self._queue.full():
                try:
                    self._queue.get_nowait()
                except Exception:
                    pass
            self._queue.put_nowait(audio.pcm_bytes)
            return True
        except Exception:
            return False

    def stop(self) -> None:
        self._stop.set()
        try:
            self._thread.join(timeout=0.5)
        except Exception:
            pass

    def _find_device(self, sd, name_contains: str) -> Optional[int]:
        try:
            devices = sd.query_devices()
            for idx, dev in enumerate(devices):
                if dev.get('max_output_channels', 0) > 0 and name_contains.lower() in dev.get('name', '').lower():
                    return idx
        except Exception:
            pass
        return None

    def _worker(self):
        try:
            import sounddevice as sd
            import numpy as np
        except ImportError:
            return
        device_idx = self._find_device(sd, self.name_contains)
        while not self._stop.is_set():
            try:
                wav_bytes = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                with wave.open(io.BytesIO(wav_bytes), 'rb') as wf:
                    sr = wf.getframerate() or self.sample_rate_fallback
                    n_channels = wf.getnchannels()
                    sampwidth = wf.getsampwidth()
                    frames = wf.readframes(wf.getnframes())
                if sampwidth != 2:
                    continue  # Only support 16-bit PCM
                arr = np.frombuffer(frames, dtype=np.int16)
                if n_channels > 1:
                    arr = arr.reshape(-1, n_channels)
                # Re-query device if not found
                if device_idx is None:
                    device_idx = self._find_device(sd, self.name_contains)
                    if device_idx is None:
                        continue  # Drop if still not found
                try:
                    sd.play(arr, sr, device=device_idx, blocking=True)
                except Exception:
                    continue
            except Exception:
                continue
import io
