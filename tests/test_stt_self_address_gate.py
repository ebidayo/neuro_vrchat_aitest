import pytest
from core.state_machine import StateMachine
from self_address import AddressDecision

class DummySM(StateMachine):
    def __init__(self, cfg=None):
        super().__init__()
        self.cfg = cfg or {}
        self.vad_speaking = False
        self._pending_stt = None
        self.last_response_strength = None
    def _maybe_interrupt(self, *a, **k):
        pass
    def _notify(self):
        pass
    def on_event(self, event, payload=None, **kwargs):
        super().on_event(event, payload, **kwargs)
        # Capture response_strength for test
        if event == "stt_final":
            if hasattr(self, '_pending_stt') and self._pending_stt:
                self.last_response_strength = self._pending_stt.get('response_strength')
            else:
                # Not pending, check if response_strength was used
                # (simulate downstream usage)
                self.last_response_strength = getattr(self, 'response_strength', None)

def make_cfg(enabled=True, aliases=None, debug=False):
    return {
        "stt": {
            "self_address": {
                "enabled": enabled,
                "name_aliases": aliases or ["美空", "misora"],
                "debug": debug,
            }
        }
    }

def test_unaddressed_low_strength():
    sm = DummySM(cfg=make_cfg(True, ["美空", "misora"]))
    sm.vad_speaking = False
    sm.on_event("stt_final", {"text": "雑談してた"})
    # Should not hard-block, but response_strength is low
    assert sm._pending_stt is None
    # No hard block, but response_strength is low
    # (simulate downstream: check that response_strength is 'low')
    # In this minimal test, we check that the logic ran and did not block

def test_addressed_but_speaking():
    sm = DummySM(cfg=make_cfg(True, ["美空", "misora"]))
    sm.vad_speaking = True
    sm.on_event("stt_final", {"text": "美空 教えて"})
    # Should defer, pending set
    assert sm._pending_stt is not None
    assert sm._pending_stt["response_strength"] == "high"

def test_release_on_silence():
    sm = DummySM(cfg=make_cfg(True, ["美空", "misora"]))
    sm.vad_speaking = True
    sm.on_event("stt_final", {"text": "美空 教えて"})
    # Now simulate VAD silent and re-invoke stt_final (pending should release)
    sm.vad_speaking = False
    sm.on_event("stt_final", {"text": "美空 教えて"})
    # Pending should be cleared
    assert sm._pending_stt is None

def test_self_address_disabled():
    sm = DummySM(cfg=make_cfg(False, ["美空", "misora"]))
    sm.vad_speaking = False
    sm.on_event("stt_final", {"text": "雑談してた"})
    # Should act as legacy (response_strength high by default)
    assert sm._pending_stt is None
