import io
import wave
from typing import Optional

def try_get_wav_duration_ms(wav_bytes: bytes) -> Optional[int]:
    try:
        with wave.open(io.BytesIO(wav_bytes), 'rb') as wf:
            framerate = wf.getframerate()
            nframes = wf.getnframes()
            if framerate > 0:
                return int(nframes * 1000 / framerate)
    except Exception:
        pass
    return None
