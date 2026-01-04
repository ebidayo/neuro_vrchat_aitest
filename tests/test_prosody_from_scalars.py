from tts_style_bert_vits2 import prosody_from_scalars, Prosody

class DummyScalars:
    def __init__(self, valence, arousal, interest):
        self.valence = valence
        self.arousal = arousal
        self.interest = interest

def test_determinism():
    s = DummyScalars(0.1, 0.2, 0.3)
    p1 = prosody_from_scalars(s)
    p2 = prosody_from_scalars(s)
    assert p1 == p2

def test_bounds():
    # arousal bounds
    s = DummyScalars(0, 10, 0)
    p = prosody_from_scalars(s)
    assert p.speaking_rate == 1.2000
    s = DummyScalars(0, -10, 0)
    p = prosody_from_scalars(s)
    assert p.speaking_rate == 0.8500
    # valence bounds
    s = DummyScalars(10, 0, 0)
    p = prosody_from_scalars(s)
    assert p.pitch_shift == 0.2000
    s = DummyScalars(-10, 0, 0)
    p = prosody_from_scalars(s)
    assert p.pitch_shift == -0.2000
    # interest bounds
    s = DummyScalars(0, 0, 10)
    p = prosody_from_scalars(s)
    assert p.energy == 1.2500
    s = DummyScalars(0, 0, -10)
    p = prosody_from_scalars(s)
    assert p.energy == 0.9000
