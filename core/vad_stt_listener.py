"""VAD + STT listener

- Captures microphone audio using sounddevice at 16kHz mono.
- Uses webrtcvad for VAD (frame_ms=30 recommended).
- Buffers utterances; when speech end detected, pushes PCM16 wav to worker queue.
- Worker thread runs faster-whisper transcription (model lazy-loaded) and calls on_transcript(text).

Notes:
- All heavy work (STT) runs in worker thread.
- Callbacks may be invoked from worker thread.
"""
import threading
import queue
import time
import logging
import tempfile
import wave
import os
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Optional dependencies: import at runtime and fall back gracefully
try:
    import webrtcvad
    import sounddevice as sd
    import numpy as np
    _HAS_AUDIO = True
except Exception as e:
    logger.warning("Audio/VAD dependencies not available: %s", e)
    _HAS_AUDIO = False

# faster-whisper import will be attempted in worker thread lazily


class VadSttListener:
    def __init__(
        self,
        on_talk_start: Callable[[], None],
        on_talk_end: Callable[[], None],
        on_transcript: Callable[[str], None],
        sample_rate: int = 16000,
        frame_ms: int = 30,
        aggressiveness: int = 2,
        start_frames: int = 3,
        end_silence_ms: int = 700,
        max_utterance_s: int = 60,
        stt_model_size: str = "small",
    ):
        self.on_talk_start = on_talk_start
        self.on_talk_end = on_talk_end
        self.on_transcript = on_transcript
        self.sample_rate = sample_rate
        self.frame_ms = frame_ms
        self.aggressiveness = aggressiveness
        self.start_frames = start_frames
        self.end_silence_ms = end_silence_ms
        self.max_utterance_s = max_utterance_s
        self.stt_model_size = stt_model_size

        self._stream: Optional[sd.InputStream] = None if _HAS_AUDIO else None
        self._vad = webrtcvad.Vad(aggressiveness) if _HAS_AUDIO else None
        self._running = False

        self._buffered_frames = []  # list of bytes
        self._in_speech = False
        self._start_count = 0
        self._silence_ms = 0
        self._utterance_start_ts = 0.0

        # queue for worker thread (holds bytes arrays)
        self._queue: queue.Queue = queue.Queue(maxsize=8)
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_stop = threading.Event()

    def start(self) -> None:
        if not _HAS_AUDIO:
            logger.warning("VAD/STT not available: missing dependencies")
            return
        if self._running:
            return
        self._running = True
        # start worker
        self._worker_thread.start()
        # stream callback expects frames of length corresponding to frame_ms
        samples_per_frame = int(self.sample_rate * (self.frame_ms / 1000.0))

        def callback(indata, frames, time_info, status):
            if status:
                logger.debug("InputStream status: %s", status)
            # indata is shape (frames, channels); expect mono
            try:
                data = indata[:, 0]
            except Exception:
                data = indata
            # ensure int16
            if data.dtype != np.int16:
                # convert float32 [-1,1] to int16
                data = np.asarray(data * 32767, dtype=np.int16)
            pcm_bytes = data.tobytes()
            self._process_frame(pcm_bytes)

        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype='int16',
                blocksize=samples_per_frame,
                callback=callback,
            )
            self._stream.start()
            logger.info("VAD/STT listener started (sr=%s frame_ms=%s)", self.sample_rate, self.frame_ms)
        except Exception as e:
            logger.exception("Failed to start input stream: %s", e)
            self._running = False

    def stop(self) -> None:
        self._running = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
        self._worker_stop.set()
        # wake worker if waiting
        try:
            self._queue.put(None, timeout=0.1)
        except Exception:
            pass
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)

    def _process_frame(self, frame_bytes: bytes) -> None:
        if not self._vad:
            return
        is_speech = self._vad.is_speech(frame_bytes, sample_rate=self.sample_rate)
        # duration tracking
        frame_ms = self.frame_ms
        if self._in_speech:
            if is_speech:
                self._buffered_frames.append(frame_bytes)
                self._silence_ms = 0
            else:
                self._silence_ms += frame_ms
                if self._silence_ms >= self.end_silence_ms:
                    # end utterance
                    self._finalize_utterance()
            # safety: check max length
            if time.time() - self._utterance_start_ts > self.max_utterance_s:
                logger.info("Max utterance length reached; finalizing")
                self._finalize_utterance()
        else:
            if is_speech:
                self._start_count += 1
                self._buffered_frames.append(frame_bytes)
                if self._start_count >= self.start_frames:
                    # start of speech
                    self._in_speech = True
                    self._utterance_start_ts = time.time()
                    self._silence_ms = 0
                    try:
                        self.on_talk_start()
                    except Exception:
                        logger.exception("on_talk_start callback failed")
            else:
                self._start_count = 0
                # keep minimal pre-buffer? we already appended frame when is_speech detected

    def _finalize_utterance(self) -> None:
        if not self._buffered_frames:
            self._in_speech = False
            self._start_count = 0
            self._silence_ms = 0
            return
        # join frames
        pcm_data = b"".join(self._buffered_frames)
        self._buffered_frames = []
        self._in_speech = False
        self._start_count = 0
        self._silence_ms = 0
        self._utterance_start_ts = 0.0

        # call end callback
        try:
            self.on_talk_end()
        except Exception:
            logger.exception("on_talk_end callback failed")

        # push to transcription queue (non-blocking)
        try:
            self._queue.put_nowait(pcm_data)
        except queue.Full:
            logger.warning("STT queue full, dropping utterance")

    def _worker_loop(self) -> None:
        model = None
        while not self._worker_stop.is_set():
            try:
                item = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if item is None:
                break
            pcm_data: bytes = item
            # write to temporary wav file
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tf:
                    wav_path = tf.name
                # write PCM16 wav
                with wave.open(wav_path, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(self.sample_rate)
                    wf.writeframes(pcm_data)

                # lazy load model
                if model is None:
                    try:
                        from faster_whisper import WhisperModel
                        model = WhisperModel(self.stt_model_size, device="cpu", compute_type="int8")
                        logger.info("Loaded faster-whisper model: %s", self.stt_model_size)
                    except Exception as e:
                        logger.exception("Failed to load faster-whisper: %s", e)
                        model = None

                transcript_text = ""
                if model is not None:
                    try:
                        segments, info = model.transcribe(wav_path, beam_size=1, language="ja")
                        parts = [seg.text for seg in segments]
                        transcript_text = " ".join(parts).strip()
                    except Exception:
                        logger.exception("Transcription failed for %s", wav_path)
                else:
                    logger.warning("No STT model available; skipping transcription")

                if transcript_text:
                    try:
                        self.on_transcript(transcript_text)
                    except Exception:
                        logger.exception("on_transcript callback failed")
                else:
                    logger.info("Transcription empty for utterance")

            finally:
                try:
                    os.remove(wav_path)
                except Exception:
                    pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    # demo usage: print callbacks
    def _on_start():
        print("talk_start")
    def _on_end():
        print("talk_end")
    def _on_trans(t):
        print("TRANSCRIPT:", t)

    v = VadSttListener(_on_start, _on_end, _on_trans)
    v.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        v.stop()
