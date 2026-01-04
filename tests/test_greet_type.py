from datetime import datetime

from core.utils.time_utils import decide_greet_type, decide_greet_type_from_dt
from main import resolve_greet_config


def test_decide_greet_type_basic():
    assert decide_greet_type(6) == "morning"
    assert decide_greet_type(13) == "day"
    assert decide_greet_type(21) == "night"
    assert decide_greet_type(2) == "night"


def test_decide_greet_type_from_dt():
    dt = datetime(2026, 1, 1, 6, 0, 0)
    assert decide_greet_type_from_dt(dt) == "morning"
    dt = datetime(2026, 1, 1, 13, 0, 0)
    assert decide_greet_type_from_dt(dt) == "day"


def test_resolve_greet_config():
    cfg = {"greet": {"enabled": False, "cooldown_sec": 10.5, "min_silence_sec": 2.5, "min_conf": 0.7, "requires_known_name": False}}
    out = resolve_greet_config(cfg)
    assert out["enabled"] is False
    assert out["cooldown_sec"] == 10.5
    assert out["min_silence_sec"] == 2.5
    assert out["min_conf"] == 0.7
    assert out["requires_known_name"] is False
