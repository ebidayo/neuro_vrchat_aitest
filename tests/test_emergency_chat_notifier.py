import pytest
from core.emergency_chat_notifier import EmergencyChatNotifier

class MockTimeProvider:
    def __init__(self, times):
        self.times = times
        self.idx = 0
    def now(self):
        t = self.times[self.idx]
        self.idx += 1
        return t

class MockChatSender:
    def __init__(self):
        self.sent = []
    def __call__(self, msg):
        self.sent.append(msg)

@pytest.fixture
def base_cfg():
    return {
        'enable_emergency_chat_jp': True,
        'emergency_chat_cooldown_sec': 120,
        'disaster_chat_cooldown_sec': 10,
        'emergency_chat_dedupe_window_sec': 600,
        'emergency_chat_max_lines': 4,
        'emergency_chat_max_chars': 180,
        'emergency_chat_prefix': '【緊急】',
        'disaster_chat_prefix': '【緊急】',
    }

def test_emergency_cooldown(base_cfg):
    tp = MockTimeProvider([0, 10, 130])
    sender = MockChatSender()
    n = EmergencyChatNotifier(sender, tp, base_cfg)
    n.maybe_notify('emergency', 'resource_danger')
    n.maybe_notify('emergency', 'resource_danger')  # within cooldown
    n.maybe_notify('emergency', 'resource_danger')  # after cooldown
    assert len(sender.sent) == 2

def test_disaster_cooldown(base_cfg):
    tp = MockTimeProvider([0, 5, 15])
    sender = MockChatSender()
    n = EmergencyChatNotifier(sender, tp, base_cfg)
    n.maybe_notify('disaster', 'disaster_watch')
    n.maybe_notify('disaster', 'disaster_watch')  # within cooldown
    n.maybe_notify('disaster', 'disaster_watch')  # after cooldown
    assert len(sender.sent) == 2

def test_dedupe(base_cfg):
    tp = MockTimeProvider([0, 1, 2, 601])
    sender = MockChatSender()
    n = EmergencyChatNotifier(sender, tp, base_cfg)
    n.maybe_notify('emergency', 'resource_danger')
    n.maybe_notify('emergency', 'resource_danger')  # dedupe window
    n.maybe_notify('emergency', 'resource_danger')  # dedupe window
    n.maybe_notify('emergency', 'resource_danger')  # after dedupe window
    assert len(sender.sent) == 2


def test_content_change_bypasses_cooldown(base_cfg):
    tp = MockTimeProvider([0, 1, 2])
    sender = MockChatSender()
    n = EmergencyChatNotifier(sender, tp, base_cfg)
    n.maybe_notify('emergency', 'resource_danger')  # A
    n.maybe_notify('emergency', 'audio_failure')    # B, different content, should send immediately
    n.maybe_notify('emergency', 'audio_failure')    # B again, within cooldown, should not send
    assert len(sender.sent) == 2
    assert sender.sent[0] != sender.sent[1]

def test_same_content_respects_cooldown(base_cfg):
    tp = MockTimeProvider([0, 1, 121])
    sender = MockChatSender()
    n = EmergencyChatNotifier(sender, tp, base_cfg)
    n.maybe_notify('emergency', 'resource_danger')  # t=0
    n.maybe_notify('emergency', 'resource_danger')  # t=1, within cooldown, should not send
    n.maybe_notify('emergency', 'resource_danger')  # t=121, after cooldown, should send
    assert len(sender.sent) == 2
    assert sender.sent[0] == sender.sent[1]

def test_disaster_fixed_template(base_cfg):
    tp = MockTimeProvider([0, 1])
    sender = MockChatSender()
    n = EmergencyChatNotifier(sender, tp, base_cfg)
    n.maybe_notify('disaster', 'any_reason')
    assert len(sender.sent) == 1
    expected = '【緊急】\n災害の可能性があります。\n安全を最優先してください。'
    assert sender.sent[0] == expected

def test_fail_soft(base_cfg):
    tp = MockTimeProvider([0])
    def bad_sender(msg):
        raise RuntimeError('fail')
    n = EmergencyChatNotifier(bad_sender, tp, base_cfg)
    n.maybe_notify('emergency', 'resource_danger')  # should not raise

def test_disabled():
    tp = MockTimeProvider([0])
    sender = MockChatSender()
    cfg = {'enable_emergency_chat_jp': False}
    n = EmergencyChatNotifier(sender, tp, cfg)
    n.maybe_notify('emergency', 'resource_danger')
    assert not sender.sent

def test_level_routing(base_cfg):
    tp = MockTimeProvider([0, 1, 12, 130])
    sender = MockChatSender()
    n = EmergencyChatNotifier(sender, tp, base_cfg)
    n.maybe_notify('emergency', 'resource_danger')
    n.maybe_notify('disaster', 'disaster_watch')
    n.maybe_notify('emergency', 'resource_danger')  # after cooldown
    assert len(sender.sent) == 3
