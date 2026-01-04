import math, io, wave, struct

def make_beep_wav_bytes(freq_hz: int, duration_ms: int, gain: float, sample_rate: int = 48000) -> bytes:
    duration_s = duration_ms / 1000.0
    n_samples = int(sample_rate * duration_s)
    fade_samples = int(sample_rate * 0.008)  # 8ms fade
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for i in range(n_samples):
            t = i / sample_rate
            # Sine wave
            s = math.sin(2 * math.pi * freq_hz * t)
            # Fade in/out
            if i < fade_samples:
                s *= i / fade_samples
            elif i > n_samples - fade_samples:
                s *= (n_samples - i) / fade_samples
            # Clamp
            v = int(max(-1, min(1, s * gain)) * 32767)
            wf.writeframesraw(struct.pack('<h', v))
    return buf.getvalue()
