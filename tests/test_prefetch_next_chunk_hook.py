from tts_style_bert_vits2 import prosody_from_scalars

def maybe_prefetch_next_chunk(tts, chunks, idx, scalars, cfg, logger):
    if not (cfg.get('tts.enabled', False) and cfg.get('tts.prefetch', False)):
        return
    if not (tts and hasattr(tts, 'is_available') and tts.is_available()):
        return
    if idx+1 >= len(chunks):
        return
    next_chunk = chunks[idx+1]
    chunk_id = getattr(next_chunk, 'id', None) or f"{hash((next_chunk.text, idx+1))}"
    try:
        tts.prefetch(next_chunk.text, prosody_from_scalars(scalars), chunk_id=chunk_id)
    except Exception:
        pass

class FakeTTS:
    def __init__(self):
        self.calls = []
    def is_available(self):
        return True
    def prefetch(self, text, prosody, chunk_id=None):
        self.calls.append((text, prosody, chunk_id))

class DummyChunk:
    def __init__(self, text, id=None):
        self.text = text
        self.id = id

class DummyScalars:
    def __init__(self, valence, arousal, interest):
        self.valence = valence
        self.arousal = arousal
        self.interest = interest

def test_prefetch_called():
    tts = FakeTTS()
    chunks = [DummyChunk("a", "c1"), DummyChunk("b", "c2")]
    scalars = DummyScalars(0,0,0)
    cfg = {'tts.enabled': True, 'tts.prefetch': True}
    logger = None
    maybe_prefetch_next_chunk(tts, chunks, 0, scalars, cfg, logger)
    assert len(tts.calls) == 1
    assert tts.calls[0][0] == "b"
    assert tts.calls[0][2] == "c2"

def test_prefetch_not_called_when_disabled():
    tts = FakeTTS()
    chunks = [DummyChunk("a", "c1"), DummyChunk("b", "c2")]
    scalars = DummyScalars(0,0,0)
    cfg = {'tts.enabled': False, 'tts.prefetch': True}
    logger = None
    maybe_prefetch_next_chunk(tts, chunks, 0, scalars, cfg, logger)
    assert len(tts.calls) == 0

def test_prefetch_not_called_when_unavailable():
    class UnavailTTS(FakeTTS):
        def is_available(self):
            return False
    tts = UnavailTTS()
    chunks = [DummyChunk("a", "c1"), DummyChunk("b", "c2")]
    scalars = DummyScalars(0,0,0)
    cfg = {'tts.enabled': True, 'tts.prefetch': True}
    logger = None
    maybe_prefetch_next_chunk(tts, chunks, 0, scalars, cfg, logger)
    assert len(tts.calls) == 0
