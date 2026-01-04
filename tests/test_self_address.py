import pytest
from self_address import detect_self_address, AddressDecision

def test_name_call_alone():
    aliases = ["ai", "えーあい", "neuro", "ねうろ", "ニューロ"]
    dec = detect_self_address("ai", name_aliases=aliases)
    assert dec.addressed is True
    assert dec.score == 0.6000
    assert "name" in dec.reason

def test_request_question_no_name():
    aliases = ["ai", "えーあい", "neuro", "ねうろ", "ニューロ"]
    dec = detect_self_address("教えて どう", name_aliases=aliases)
    assert dec.addressed is False
    assert dec.score == 0.4000
    assert "req" in dec.reason and "q" in dec.reason

def test_name_and_request():
    aliases = ["ai", "えーあい", "neuro", "ねうろ", "ニューロ"]
    dec = detect_self_address("ai 教えて", name_aliases=aliases)
    assert dec.addressed is True
    assert dec.score == 0.8000
    assert "name" in dec.reason and "req" in dec.reason

def test_third_person_negative():
    aliases = ["ai", "えーあい", "neuro", "ねうろ", "ニューロ"]
    dec = detect_self_address("ai って言ってた", name_aliases=aliases)
    assert dec.addressed is False
    assert dec.score == 0.1000
    assert "-3p" in dec.reason

def test_clamp_lower_bound():
    aliases = ["ai", "えーあい", "neuro", "ねうろ", "ニューロ"]
    dec = detect_self_address("って言ってた", name_aliases=aliases)
    assert dec.addressed is False
    assert dec.score == 0.0000
    assert "-3p" in dec.reason

def test_determinism():
    aliases = ["ai", "えーあい", "neuro", "ねうろ", "ニューロ"]
    dec1 = detect_self_address("ai 教えて", name_aliases=aliases)
    dec2 = detect_self_address("ai 教えて", name_aliases=aliases)
    assert dec1 == dec2
