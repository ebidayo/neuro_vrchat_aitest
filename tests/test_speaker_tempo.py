import pytest
from speaker_tempo import compute_speaker_tempo

class DummyStore:
    def __init__(self, rec=0.0, usage=0.0, interest=0.0):
        self.rec = rec
        self.usage = usage
        self.interest = interest
    def get_recency(self, k, now):
        return self.rec
    def get_avatar_usage(self, k, now):
        return self.usage
    def get_interest(self, k, now):
        return self.interest

def test_tempo_default():
    t = compute_speaker_tempo(None, None, 12345)
    assert t['response_delay_ms'] == 0
    assert t['idle_interval_scale'] == 1.0
    assert t['prosody_speed_scale'] == 1.0

def test_tempo_inactive():
    store = DummyStore(0.0, 0.0, 0.0)
    t = compute_speaker_tempo('A', store, 12345)
    assert t['response_delay_ms'] == 800
    assert 1.19 < t['idle_interval_scale'] <= 1.2
    assert 0.69 < t['prosody_speed_scale'] <= 0.7

def test_tempo_active():
    store = DummyStore(1.0, 1.0, 1.0)
    t = compute_speaker_tempo('A', store, 12345)
    assert t['response_delay_ms'] == 0
    assert 0.69 < t['idle_interval_scale'] < 0.8
    assert 1.19 < t['prosody_speed_scale'] <= 1.2

def test_tempo_mixed():
    store = DummyStore(0.5, 0.2, 0.3)
    t = compute_speaker_tempo('A', store, 12345)
    assert 0 <= t['response_delay_ms'] <= 800
    assert 0.7 <= t['idle_interval_scale'] <= 1.2
    assert 0.7 <= t['prosody_speed_scale'] <= 1.2

def test_tempo_failsoft():
    class BadStore:
        def get_recency(self, k, n): raise Exception()
        def get_avatar_usage(self, k, n): raise Exception()
        def get_interest(self, k, n): raise Exception()
    t = compute_speaker_tempo('A', BadStore(), 12345)
    assert t['response_delay_ms'] == 0
    assert t['idle_interval_scale'] == 1.0
    assert t['prosody_speed_scale'] == 1.0
