from main import emit_chunk
import pytest

class DummyOsc:
    def __init__(self):
        self.sent = []
    def send_avatar_params(self, params):
        self.sent.append(params)
    def send_chatbox(self, text, send_immediately=True, notify=False):
        pass

def test_emit_chunk_interest_valence(monkeypatch):
    # Setup dummy params_map with interest and valence
    params_map = {
        "valence": "Mood",
        "interest": "InterestLevel"
    }
    # Chunk with both osc and interest
    chunk = {
        "id": "test1",
        "type": "say",
        "text": "test",
        "pause_ms": 0,
        "osc": {"N_Valence": 0.7},
        "interest": 0.5
    }
    osc = DummyOsc()
    # Dummy state and sm
    class DummyState:
        name = "TALK"
    class DummySM:
        def __init__(self):
            self.state = DummyState()
    import asyncio
    asyncio.run(emit_chunk(chunk, osc, params_map, DummyState(), DummySM(), mode="debug"))
    # Should send both Mood and InterestLevel
    sent = osc.sent[0]
    assert sent["Mood"] == 0.7
    assert sent["InterestLevel"] == 0.5

def test_emit_chunk_interest_only(monkeypatch):
    params_map = {"interest": "InterestLevel"}
    chunk = {"id": "test2", "type": "say", "text": "test", "pause_ms": 0, "interest": 0.9}
    osc = DummyOsc()
    class DummyState:
        name = "TALK"
    class DummySM:
        def __init__(self):
            self.state = DummyState()
    import asyncio
    asyncio.run(emit_chunk(chunk, osc, params_map, DummyState(), DummySM(), mode="debug"))
    sent = osc.sent[0]
    assert sent["InterestLevel"] == 0.9

def test_emit_chunk_interest_clamp(monkeypatch):
    params_map = {"interest": "InterestLevel"}
    chunk = {"id": "test3", "type": "say", "text": "test", "pause_ms": 0, "interest": 2.0}
    osc = DummyOsc()
    class DummyState:
        name = "TALK"
    class DummySM:
        def __init__(self):
            self.state = DummyState()
    import asyncio
    asyncio.run(emit_chunk(chunk, osc, params_map, DummyState(), DummySM(), mode="debug"))
    sent = osc.sent[0]
    assert sent["InterestLevel"] == 1.0


# --- 追加: interest→表情 係数テスト ---
import math

def get_face_valence(base_valence, interest_norm, gain=0.35, maxval=0.6):
    # Clamp interest_norm to [0,1] at the top to match test expectation
    interest_norm = max(0.0, min(1.0, interest_norm))
    if base_valence == 0.0:
        return 0.0
    sign = 1.0 if base_valence > 0 else -1.0
    interest_face = max(0.0, min(maxval, interest_norm * gain))
    return max(-1.0, min(1.0, base_valence + sign * interest_face))

@pytest.mark.parametrize("base_valence,interest_norm,expected", [  # gain=0.35, max=0.6
    (0.5, 1.0, get_face_valence(0.5, 1.0)),   # 0.5+0.35=0.85
    (0.5, 0.0, get_face_valence(0.5, 0.0)),   # 0.5+0=0.5
    (0.5, 2.0, get_face_valence(0.5, 1.0)),   # clamp interest_norm to 1.0
    (-0.5, 1.0, get_face_valence(-0.5, 1.0)), # -0.5-0.35=-0.85
    (-0.5, 0.0, get_face_valence(-0.5, 0.0)), # -0.5-0=-0.5
    (0.0, 1.0, 0.0),                         # valence=0→interest加算なし
    (0.0, 0.0, 0.0),
    (1.0, 1.0, get_face_valence(1.0, 1.0)),   # 1.0+0.35=1.0 (clamped)
    (-1.0, 1.0, get_face_valence(-1.0, 1.0)), # -1.0-0.35=-1.0 (clamped)
])
def test_face_valence_formula(base_valence, interest_norm, expected):
    # 検算: main.pyのロジックと一致すること
    result = get_face_valence(base_valence, interest_norm)
    assert math.isclose(result, expected, abs_tol=1e-6)

def test_emit_chunk_face_valence(monkeypatch):
    params_map = {"valence": "Mood", "interest": "InterestLevel"}
    osc = DummyOsc()
    class DummyState:
        name = "TALK"
    class DummySM:
        def __init__(self):
            self.state = DummyState()
    import asyncio
    # interest高, valence正
    chunk = {"id": "fv1", "type": "say", "text": "test", "pause_ms": 0, "osc": {"N_Valence": 0.5}, "interest": 1.0}
    asyncio.run(emit_chunk(chunk, osc, params_map, DummyState(), DummySM(), mode="debug"))
    sent = osc.sent[-1]
    assert math.isclose(sent["Mood"], get_face_valence(0.5, 1.0), abs_tol=1e-6)
    # interest高, valence負
    chunk = {"id": "fv2", "type": "say", "text": "test", "pause_ms": 0, "osc": {"N_Valence": -0.5}, "interest": 1.0}
    asyncio.run(emit_chunk(chunk, osc, params_map, DummyState(), DummySM(), mode="debug"))
    sent = osc.sent[-1]
    assert math.isclose(sent["Mood"], get_face_valence(-0.5, 1.0), abs_tol=1e-6)
    # valence=0→interest加算なし
    chunk = {"id": "fv3", "type": "say", "text": "test", "pause_ms": 0, "osc": {"N_Valence": 0.0}, "interest": 1.0}
    asyncio.run(emit_chunk(chunk, osc, params_map, DummyState(), DummySM(), mode="debug"))
    sent = osc.sent[-1]
    assert sent["Mood"] == 0.0
    # interest=0→valenceのみ
    chunk = {"id": "fv4", "type": "say", "text": "test", "pause_ms": 0, "osc": {"N_Valence": 0.5}, "interest": 0.0}
    asyncio.run(emit_chunk(chunk, osc, params_map, DummyState(), DummySM(), mode="debug"))
    sent = osc.sent[-1]
    assert sent["Mood"] == 0.5
    # clamping: valence+interest超過
    chunk = {"id": "fv5", "type": "say", "text": "test", "pause_ms": 0, "osc": {"N_Valence": 1.0}, "interest": 1.0}
    asyncio.run(emit_chunk(chunk, osc, params_map, DummyState(), DummySM(), mode="debug"))
    sent = osc.sent[-1]
    assert sent["Mood"] == 1.0
    chunk = {"id": "fv6", "type": "say", "text": "test", "pause_ms": 0, "osc": {"N_Valence": -1.0}, "interest": 1.0}
    asyncio.run(emit_chunk(chunk, osc, params_map, DummyState(), DummySM(), mode="debug"))
    sent = osc.sent[-1]
    assert sent["Mood"] == -1.0
