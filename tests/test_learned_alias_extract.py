import pytest
from learned_alias import normalize_for_alias, extract_candidate_alias, filter_candidate

def make_cfg(**kw):
    cfg = {
        "min_len": 2,
        "max_len": 8,
        "forbid_tokens": ["バカ"],
        "allow_latin": True,
        "allow_kana": True,
        "allow_kanji": False,
    }
    cfg.update(kw)
    return cfg

def test_extract_patterns():
    norm = normalize_for_alias("misoって呼んで")
    out = extract_candidate_alias(norm, min_len=2, max_len=8)
    assert out == ["miso"]
    norm = normalize_for_alias("呼び方はmira")
    out = extract_candidate_alias(norm, min_len=2, max_len=8)
    assert out == ["mira"]
    norm = normalize_for_alias("あだ名はmikuでお願い")
    out = extract_candidate_alias(norm, min_len=2, max_len=8)
    assert out == ["miku"]

def test_forbidden_token():
    norm = normalize_for_alias("バカって呼んで")
    out = extract_candidate_alias(norm, min_len=2, max_len=8, forbid_tokens=["バカ"])
    assert out == []

def test_length_bounds():
    norm = normalize_for_alias("abって呼んで")
    out = extract_candidate_alias(norm, min_len=3, max_len=8)
    assert out == []
    norm = normalize_for_alias("abcdefghijkって呼んで")
    out = extract_candidate_alias(norm, min_len=2, max_len=8)
    assert out == []

def test_filter_candidate():
    cfg = make_cfg()
    assert filter_candidate("miso", cfg)
    assert not filter_candidate("バカ", cfg)
    assert not filter_candidate("abcdefghijk", cfg)
    assert not filter_candidate("a b", cfg)
