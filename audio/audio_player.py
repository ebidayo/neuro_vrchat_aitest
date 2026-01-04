def play_wav_bytes(wav_bytes: bytes) -> bool:
    """Play WAV audio from bytes. Return True on success, False on fail (never raise)."""
    if not sa or not wav_bytes:
        return False
    try:
        wave_obj = sa.WaveObject.from_wave_read(sa.WaveObject(io.BytesIO(wav_bytes)))
        play_obj = wave_obj.play()
        play_obj.wait_done()
        return True
    except Exception:
        return False
import os
try:
    import simpleaudio as sa
except ImportError:
    sa = None

def play_wav(path: str) -> bool:
    """Play a WAV file. Return True on success, False on fail (never raise)."""
    if not sa or not os.path.exists(path):
        return False
    try:
        wave_obj = sa.WaveObject.from_wave_file(path)
        play_obj = wave_obj.play()
        play_obj.wait_done()
        return True
    except Exception:
        return False
