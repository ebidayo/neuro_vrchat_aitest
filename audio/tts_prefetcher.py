import threading
import hashlib
import os
import logging
from typing import Dict, Set, Optional

class TTSPrefetcher:
    def __init__(self, tts, cache_dir="tts_cache"):
        self.tts = tts
        self.cache: Dict[str, str] = {}
        self.in_flight: Set[str] = set()
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        self.lock = threading.Lock()
        self.log = logging.getLogger("TTSPrefetcher")

    def _key(self, chunk, prosody_signature):
        h = hashlib.sha256()
        h.update((chunk.text + prosody_signature).encode("utf-8"))
        return h.hexdigest()

    def prefetch(self, chunk, prosody_signature):
        key = self._key(chunk, prosody_signature)
        with self.lock:
            if key in self.cache or key in self.in_flight:
                return
            self.in_flight.add(key)
        def run():
            try:
                wav_path = os.path.join(self.cache_dir, f"{key}.wav")
                if not os.path.exists(wav_path):
                    wav = self.tts.synthesize(chunk.text, prosody=chunk.prosody)
                    if wav:
                        with open(wav_path, "wb") as f:
                            f.write(wav)
                with self.lock:
                    self.cache[key] = wav_path
            except Exception as e:
                self.log.debug(f"Prefetch failed: {e}")
            finally:
                with self.lock:
                    self.in_flight.discard(key)
        t = threading.Thread(target=run, daemon=True)
        t.start()

    def get(self, chunk, prosody_signature) -> Optional[str]:
        key = self._key(chunk, prosody_signature)
        with self.lock:
            return self.cache.get(key)

    def drop(self, chunk, prosody_signature):
        key = self._key(chunk, prosody_signature)
        with self.lock:
            path = self.cache.pop(key, None)
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception as e:
                self.log.debug(f"Drop failed: {e}")

    def clear(self):
        with self.lock:
            keys = list(self.cache.keys())
            self.cache.clear()
        for key in keys:
            path = os.path.join(self.cache_dir, f"{key}.wav")
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception as e:
                    self.log.debug(f"Clear failed: {e}")
        with self.lock:
            self.in_flight.clear()
