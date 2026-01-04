import sys
import types
import pytest

@pytest.fixture(autouse=True)
def patch_audio_modules(monkeypatch):
    dummy_beep_mod = types.ModuleType('audio.beep')
    dummy_beep_mod.make_beep_wav_bytes = lambda *a, **k: b'beep'
    sys.modules['audio.beep'] = dummy_beep_mod
    dummy_player_mod = types.ModuleType('audio.audio_player')
    dummy_player_mod.play_wav_bytes = lambda *a, **k: True
    sys.modules['audio.audio_player'] = dummy_player_mod
    yield
    sys.modules.pop('audio.beep', None)
    sys.modules.pop('audio.audio_player', None)



# Insert dummy audio.beep and audio.audio_player modules so imports in production always succeed
import sys
import types
dummy_beep = types.ModuleType("audio.beep")
def make_beep_wav_bytes(*args, **kwargs):
    return b"dummy-wav-bytes"
dummy_beep.make_beep_wav_bytes = make_beep_wav_bytes
sys.modules["audio.beep"] = dummy_beep
dummy_player = types.ModuleType("audio.audio_player")
def play_wav_bytes(*args, **kwargs):
    return True
dummy_player.play_wav_bytes = play_wav_bytes
sys.modules["audio.audio_player"] = dummy_player

import pytest
from core.emergency_chat_notifier import EmergencyChatNotifier


class MockTimeProvider:
    def __init__(self, times):
        self.times = times
        self.idx = 0
    def now(self):
        t = self.times[self.idx]
        self.idx = min(self.idx + 1, len(self.times) - 1)
        return t

class MockChatSender:
    def __init__(self):
        self.sent = []
    def __call__(self, msg):
        self.sent.append(msg)

class MockBeepPlayer:
    def __init__(self):
        self.calls = []
    def __call__(self, wav_bytes):
        self.calls.append(wav_bytes)


def base_cfg(**overrides):
    cfg = {
        'enable_emergency_chat_jp': True,
        'emergency_chat_cooldown_sec': 120,
        'disaster_chat_cooldown_sec': 10,
        'emergency_chat_dedupe_window_sec': 600,
        'emergency_chat_max_lines': 4,
        'emergency_chat_max_chars': 180,
        'emergency_chat_prefix': '【緊急】',
        'disaster_chat_prefix': '【緊急】',
        'enable_disaster_beep': True,
        'disaster_beep_min_interval_sec': 8,
        'disaster_beep_freq_hz': 1000,
        'disaster_beep_duration_ms': 160,
        'disaster_beep_gain': 0.25,
        'disaster_beep_repeats': 1,
        'disaster_beep_repeat_gap_ms': 120,
    }
    cfg.update(overrides)
    return cfg


def test_disaster_beep_triggers_on_send():
    cfg = base_cfg()
    tp = MockTimeProvider([0])
    chat = MockChatSender()
    calls = []
    n = EmergencyChatNotifier(chat, tp, cfg, beep_player=lambda _: calls.append(b'dummy-wav-bytes'))
    n.maybe_notify('disaster', 'disaster_watch')
    expected = '【緊急】\n災害の可能性があります。\n安全を最優先してください。'
    assert chat.sent[0] == expected
    assert len(calls) == 1


def test_no_beep_for_normal_emergency():
    cfg = base_cfg()
    tp = MockTimeProvider([0])
    chat = MockChatSender()
    calls = []
    n = EmergencyChatNotifier(chat, tp, cfg, beep_player=lambda _: calls.append(b'dummy-wav-bytes'))
    n.maybe_notify('emergency', 'resource_danger')
    assert len(chat.sent) == 1
    assert len(calls) == 0


def test_beep_respects_min_interval():
    cfg = base_cfg(disaster_beep_min_interval_sec=8)
    tp = MockTimeProvider([0, 1, 9])
    chat = MockChatSender()
    calls = []
    n = EmergencyChatNotifier(chat, tp, cfg, beep_player=lambda _: calls.append(b'dummy-wav-bytes'))
    n.maybe_notify('disaster', 'A')
    n.maybe_notify('disaster', 'B')
    n.maybe_notify('disaster', 'C')
    assert len(calls) == 2
    assert len(chat.sent) == 3


def test_beep_only_when_actually_sent():
    cfg = base_cfg(disaster_chat_cooldown_sec=120)
    tp = MockTimeProvider([0, 1])
    chat = MockChatSender()
    calls = []
    n = EmergencyChatNotifier(chat, tp, cfg, beep_player=lambda _: calls.append(b'dummy-wav-bytes'))
    n.maybe_notify('disaster', 'disaster_watch')
    n.maybe_notify('disaster', 'disaster_watch')
    assert len(chat.sent) == 1
    assert len(calls) == 1


def test_feature_disabled_no_beep():
    cfg = base_cfg(enable_disaster_beep=False)
    tp = MockTimeProvider([0])
    chat = MockChatSender()
    calls = []
    n = EmergencyChatNotifier(chat, tp, cfg, beep_player=lambda _: calls.append(b'dummy-wav-bytes'))
    n.maybe_notify('disaster', 'disaster_watch')
    assert len(chat.sent) == 1
    assert len(calls) == 0
