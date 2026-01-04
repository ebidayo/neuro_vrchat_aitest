import pytest
from core.emotion_afterglow import EmotionAfterglow

class MockTimeProvider:
    def __init__(self, times):
        self.times = times
        self.idx = 0
    def now(self):
        t = self.times[self.idx]
        self.idx += 1
        return t

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def test_basic_decay():
    tp = MockTimeProvider([0, 2, 4, 8, 16, 32])
    cfg = {'enable_emotion_afterglow': True, 'afterglow_tau_sec': 8.0, 'afterglow_tick_hz': 0.5, 'afterglow_min_delta': 0.001, 'afterglow_max_hold_sec': 60.0}
    ag = EmotionAfterglow(tp, cfg, clamp)
    ag.on_emit_end(1.0, 1.0)
    vals = []
    for _ in range(5):
        v, i = ag.tick(0.0, 0.5)
        vals.append((v, i))
    # Should monotonically approach baseline
    for j in range(1, len(vals)):
        assert abs(vals[j][0] - 0.0) < abs(vals[j-1][0] - 0.0)
        assert abs(vals[j][1] - 0.5) < abs(vals[j-1][1] - 0.5)

def test_overwrite():
    tp = MockTimeProvider([0, 2, 4, 6])
    cfg = {'enable_emotion_afterglow': True, 'afterglow_tau_sec': 8.0, 'afterglow_tick_hz': 0.5, 'afterglow_min_delta': 0.001, 'afterglow_max_hold_sec': 60.0}
    ag = EmotionAfterglow(tp, cfg, clamp)
    ag.on_emit_end(1.0, 1.0)
    ag.tick(0.0, 0.5)
    ag.on_emit_end(-1.0, 0.0)
    v, i = ag.tick(0.0, 0.5)
    assert v < 0.0 and i < 0.5

def test_stop_conditions():
    # min_delta
    tp = MockTimeProvider([0, 100])
    cfg = {'enable_emotion_afterglow': True, 'afterglow_tau_sec': 8.0, 'afterglow_tick_hz': 0.5, 'afterglow_min_delta': 0.001, 'afterglow_max_hold_sec': 60.0}
    ag = EmotionAfterglow(tp, cfg, clamp)
    ag.on_emit_end(0.01, 0.51)
    v, i = ag.tick(0.0, 0.5)
    # Should snap to baseline
    assert v == 0.0 and i == 0.5
    # max_hold
    tp2 = MockTimeProvider([0, 200])
    ag2 = EmotionAfterglow(tp2, cfg, clamp)
    ag2.on_emit_end(1.0, 1.0)
    v2, i2 = ag2.tick(0.0, 0.5)
    assert v2 == 0.0 and i2 == 0.5

def test_gating():
    tp = MockTimeProvider([0, 2])
    cfg = {'enable_emotion_afterglow': False, 'afterglow_tau_sec': 8.0, 'afterglow_tick_hz': 0.5, 'afterglow_min_delta': 0.001, 'afterglow_max_hold_sec': 60.0}
    ag = EmotionAfterglow(tp, cfg, clamp)
    ag.on_emit_end(1.0, 1.0)
    v, i = ag.tick(0.0, 0.5)
    assert v == 0.0 and i == 0.5
    # ALERT/SEARCH disables afterglow
    cfg2 = {'enable_emotion_afterglow': True, 'afterglow_tau_sec': 8.0, 'afterglow_tick_hz': 0.5, 'afterglow_min_delta': 0.001, 'afterglow_max_hold_sec': 60.0}
    ag2 = EmotionAfterglow(tp, cfg2, clamp)
    ag2.on_emit_end(1.0, 1.0)
    v2, i2 = ag2.tick(0.0, 0.5, state="ALERT")
    assert v2 == 0.0 and i2 == 0.5
