import pytest
from core.agents.finalizer_agent import FinalizerAgent

class DummyTTS:
    def __init__(self):
        self.prefetch_calls = []
        self._available = True
    def is_available(self):
        return self._available
    def prefetch(self, text, prosody, chunk_id=None):
        self.prefetch_calls.append((text, prosody, chunk_id))
    def set_available(self, val):
        self._available = val

class DummyLogger:
    def debug(self, *a, **k): pass
    def warning(self, *a, **k): pass

def make_content(n):
    return [{"type": "say", "text": f"chunk{i}", "id": f"c{i}"} for i in range(n)]

def test_finalize_no_prefetch_when_off():
    agent = FinalizerAgent()
    inp = {"edited": {"content": make_content(2)}, "scalars": {}, "limits": {}, "config": {"tts.enabled": False, "tts.prefetch": True}, "tts": DummyTTS(), "logger": DummyLogger()}
    out = agent.finalize(inp)
    assert out["ok"]
    assert len(inp["tts"].prefetch_calls) == 0

def test_finalize_prefetch_once():
    agent = FinalizerAgent()
    tts = DummyTTS()
    inp = {"edited": {"content": make_content(2)}, "scalars": {}, "limits": {}, "config": {"tts.enabled": True, "tts.prefetch": True}, "tts": tts, "logger": DummyLogger()}
    out = agent.finalize(inp)
    assert out["ok"]
    # Should prefetch exactly one next chunk
    assert len(tts.prefetch_calls) == 1
    assert tts.prefetch_calls[0][0] == "chunk1"

def test_finalize_no_prefetch_len1():
    agent = FinalizerAgent()
    tts = DummyTTS()
    inp = {"edited": {"content": make_content(1)}, "scalars": {}, "limits": {}, "config": {"tts.enabled": True, "tts.prefetch": True}, "tts": tts, "logger": DummyLogger()}
    out = agent.finalize(inp)
    assert out["ok"]
    assert len(tts.prefetch_calls) == 0

def test_finalize_missing_tts_section():
    agent = FinalizerAgent()
    tts = DummyTTS()
    inp = {"edited": {"content": make_content(2)}, "scalars": {}, "limits": {}, "config": {}, "tts": tts, "logger": DummyLogger()}
    out = agent.finalize(inp)
    assert out["ok"]
    assert len(tts.prefetch_calls) == 0
