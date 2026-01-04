import pytest
from system_monitor.resource_evaluator import evaluate_resource_state

def test_evaluate_resource_state_basic():
    # All None
    m = {'cpu': None, 'ram': None, 'gpu': None, 'vram': None}
    out = evaluate_resource_state(m)
    assert out['danger'] == 0.0
    assert out['dominant'] is None

def test_evaluate_resource_state_cpu():
    m = {'cpu': 0.8, 'ram': 0.2, 'gpu': 0.1, 'vram': 0.1}
    out = evaluate_resource_state(m)
    assert out['danger'] == pytest.approx(0.8)
    assert out['dominant'] == 'cpu'

def test_evaluate_resource_state_ram():
    m = {'cpu': 0.2, 'ram': 0.9, 'gpu': 0.1, 'vram': 0.1}
    out = evaluate_resource_state(m)
    # danger = max(0.2, 0.9*0.9, 0.1, 0.1) = 0.81
    assert out['danger'] == pytest.approx(0.81)
    assert out['dominant'] == 'ram'

def test_evaluate_resource_state_gpu_vram():
    m = {'cpu': 0.2, 'ram': 0.2, 'gpu': 0.95, 'vram': 0.8}
    out = evaluate_resource_state(m)
    assert out['danger'] == pytest.approx(0.95)
    assert out['dominant'] == 'gpu'
    m2 = {'cpu': 0.2, 'ram': 0.2, 'gpu': 0.7, 'vram': 0.99}
    out2 = evaluate_resource_state(m2)
    assert out2['danger'] == pytest.approx(0.99)
    assert out2['dominant'] == 'vram'

def test_evaluate_resource_state_clamp():
    m = {'cpu': 1.5, 'ram': -0.5, 'gpu': None, 'vram': 0.0}
    out = evaluate_resource_state(m)
    assert 0.99 <= out['danger'] <= 1.0
    assert out['dominant'] == 'cpu'
