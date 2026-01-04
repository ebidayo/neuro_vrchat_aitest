import pytest
from system_monitor.self_regulator import SelfRegulator

def test_self_regulator_ok():
    reg = SelfRegulator()
    out = reg.apply('ok')
    assert out['tts_enabled'] is True
    assert out['prosody_scale'] == 1.0
    assert out['idle_interval_scale'] == 1.0

def test_self_regulator_warn():
    reg = SelfRegulator()
    out = reg.apply('warn')
    assert out['tts_enabled'] is True
    assert 0.84 < out['prosody_scale'] < 0.86
    assert 1.29 < out['idle_interval_scale'] < 1.31

def test_self_regulator_danger():
    reg = SelfRegulator()
    out = reg.apply('danger')
    assert out['tts_enabled'] is False
    assert 0.69 < out['prosody_scale'] < 0.71
    assert 1.59 < out['idle_interval_scale'] < 1.61

def test_self_regulator_clamp():
    reg = SelfRegulator()
    # Should clamp to min/max
    out = reg.apply('danger')
    assert 0.5 <= out['prosody_scale'] <= 1.0
    assert 0.5 <= out['idle_interval_scale'] <= 2.0
    out2 = reg.apply('warn')
    assert 0.5 <= out2['prosody_scale'] <= 1.0
    assert 0.5 <= out2['idle_interval_scale'] <= 2.0

def test_self_regulator_none():
    reg = SelfRegulator()
    out = reg.apply(None)
    assert out['tts_enabled'] is True
    assert out['prosody_scale'] == 1.0
    assert out['idle_interval_scale'] == 1.0
