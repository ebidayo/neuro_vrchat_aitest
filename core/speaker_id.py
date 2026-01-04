"""Speaker identification utility (lightweight, optional dependency).

Provides a SpeakerID class with optional backends. If heavy deps are missing, falls back to disabled mode.
Includes a simple 'mock' backend for deterministic unit tests.
"""
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

try:
    import numpy as np
    HAS_NUMPY = True
except Exception:
    HAS_NUMPY = False


class MockBackend:
    def __init__(self, seed: int = 1234):
        self.seed = int(seed)
        self.enrolled = {}

    def _embed_for_name(self, name: str):
        # deterministic pseudo-embedding from name
        v = [((ord(c) % 32) - 16) / 16.0 for c in name[:16]]
        # pad/trim to 32
        v = (v + [0.0] * 32)[:32]
        # normalize
        norm = sum(x * x for x in v) ** 0.5 if v else 1.0
        return [x / (norm or 1.0) for x in v]

    def enroll(self, speaker_name: str, wav_path: Optional[str] = None, audio: Optional[Any] = None, sr: int = 16000):
        emb = self._embed_for_name(speaker_name)
        self.enrolled[speaker_name] = emb
        return emb

    def identify(self, audio: Optional[Any] = None, sr: int = 16000):
        # if audio is a string 'as_name:alice' we can extract for test convenience
        if isinstance(audio, str) and audio.startswith("as_name:"):
            name = audio.split(":", 1)[1]
            emb = self._embed_for_name(name)
        else:
            # fallback unknown embedding
            emb = [0.0] * 32
        # compute cosine similarity to enrolled
        best = None
        best_score = -1.0
        for name, e in self.enrolled.items():
            # cosine similarity
            num = sum(a * b for a, b in zip(emb, e))
            denom = (sum(a * a for a in emb) ** 0.5) * (sum(b * b for b in e) ** 0.5) or 1.0
            sim = num / denom
            if sim > best_score:
                best_score = sim
                best = name
        return {"best": best, "score": float(best_score), "embedding_norm": float(sum(x * x for x in emb) ** 0.5)}


class SpeakerID:
    def __init__(self, backend: str = "mock", threshold: float = 0.75, unknown_margin: float = 0.05):
        self.enabled = True
        self.backend_name = backend
        self.threshold = float(threshold)
        self.unknown_margin = float(unknown_margin)
        self._backend = None

        if backend == "mock":
            self._backend = MockBackend()
        else:
            # real backends not implemented in this minimal change; if numpy missing, disable
            try:
                import numpy as _np
                # placeholder: we could detect 'speechbrain' or 'resemblyzer' here
                logger.warning("Requested backend %s not available; running in disabled mode", backend)
                self.enabled = False
            except Exception:
                logger.exception("Failed to initialize backend; SpeakerID disabled")
                self.enabled = False

    def enroll(self, speaker_name: str, wav_path: Optional[str] = None, audio: Optional[Any] = None, sr: int = 16000):
        if not self.enabled:
            logger.debug("SpeakerID disabled; enroll ignored")
            return None
        return self._backend.enroll(speaker_name, wav_path=wav_path, audio=audio, sr=sr)

    def identify(self, audio: Optional[Any], sr: int = 16000) -> Dict[str, Any]:
        if not self.enabled:
            return {"speaker_id": None, "confidence": 0.0, "embedding_norm": 0.0, "matched": False}
        try:
            res = self._backend.identify(audio=audio, sr=sr)
            best = res.get("best")
            score = float(res.get("score", 0.0))
            if best is None or score < (self.threshold - self.unknown_margin):
                # treat as unknown
                return {"speaker_id": None, "confidence": score, "embedding_norm": float(res.get("embedding_norm", 0.0)), "matched": False}
            # matched enrolled
            return {"speaker_id": best, "confidence": score, "embedding_norm": float(res.get("embedding_norm", 0.0)), "matched": True}
        except Exception:
            logger.exception("Speaker identification failed")
            return {"speaker_id": None, "confidence": 0.0, "embedding_norm": 0.0, "matched": False}
