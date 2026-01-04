import time
import math
from core.memory_decay import decay_factor, apply_decay_to_counts, ewma_update

def test_decay_factor_basic():
    assert decay_factor(0, 100, 0.1) == 1.0
    assert math.isclose(decay_factor(100, 100, 0.01), 0.5)
    assert decay_factor(100, 100, 0.6) == 0.6  # floor_weight効く
    assert decay_factor(100, 0, 0.1) == 1.0  # half_life_sec<=0

def test_apply_decay_to_counts_deterministic():
    now = 1000000000  # 固定値で決定的に
    items = [
        ("a", 10, now-100),
        ("b", 20, now-200),
        ("c", 10, now-50),
    ]
    # half_life=100, floor=0.1
    out = apply_decay_to_counts(items, now, 100, 0.1)
    # スコア計算
    # a: 10 * 0.5**(100/100) = 10*0.5=5
    # b: 20 * 0.5**(200/100) = 20*0.25=5
    # c: 10 * 0.5**(50/100) = 10*0.7071...=7.071...
    # 並び: c(7.07), a(5), b(5) ただしa,bはscore同値でtoken昇順
    assert out[0][0] == "c"
    assert out[1][0] == "a"
    assert out[2][0] == "b"
    # 決定的
    assert sorted(out, key=lambda x: (-x[1], x[0])) == out

def test_ewma_update():
    assert math.isclose(ewma_update(1.0, 0.0, 0.5), 0.5)
    assert math.isclose(ewma_update(0.0, 1.0, 0.2), 0.2)
    assert math.isclose(ewma_update(0.5, 0.5, 0.1), 0.5)
