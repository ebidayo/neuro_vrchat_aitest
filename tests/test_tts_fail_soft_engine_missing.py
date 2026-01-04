import sys
import types
import builtins
import pytest
from tts_style_bert_vits2 import LocalTTS, SpeakResult, Prosody

def test_fail_soft_engine_missing():
    class DummyLogger:
        def warning(self, *a, **k):
            pass
        def debug(self, *a, **k):
            pass
    cfg = {'tts.enabled': True}
    clock = lambda: 0.0
    rng = lambda: 0.0
    tts = LocalTTS(cfg, clock, rng, DummyLogger())
    assert not tts.is_available()
    res = tts.speak("hello", Prosody(1.0,0.0,1.0), chunk_id="c1")
    assert isinstance(res, SpeakResult)
    assert not res.ok
    tts.prefetch("hello", Prosody(1.0,0.0,1.0), chunk_id="c1")  # should not raise
