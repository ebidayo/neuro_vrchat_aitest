import pytest
from self_address import detect_self_address

def test_confirmed_alias_scoring():
    # Confirmed alias should add +0.4 to score
    text = "miso 教えて"
    aliases = ["美空", "misora"]
    confirmed_aliases = ["miso"]
    decision = detect_self_address(text, name_aliases=aliases, enable_debug_reason=True, confirmed_aliases=confirmed_aliases)
    # Should be at least 0.6 (0.4 from confirmed, 0.2 from req)
    assert decision.score >= 0.6
    assert decision.addressed
    assert "confirmed" in decision.reason

def test_no_confirmed_alias():
    text = "miso 教えて"
    aliases = ["美空", "misora"]
    confirmed_aliases = []
    decision = detect_self_address(text, name_aliases=aliases, enable_debug_reason=True, confirmed_aliases=confirmed_aliases)
    # Should be below 0.6 (no fixed alias, no confirmed)
    assert decision.score < 0.6
    assert not decision.addressed
