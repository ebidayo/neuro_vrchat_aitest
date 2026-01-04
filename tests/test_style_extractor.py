import pytest
from core.style_extractor import normalize_text, tokenize_ja_simple, extract_features

def test_normalize_text():
    t = 'HELLO １２３ https://test.com @user #tag ！！！ 4444 まじwww'
    norm = normalize_text(t)
    assert '<url>' in norm and '<mention>' in norm and '<hashtag>' in norm and '<num>' in norm
    assert 'www' in norm

def test_tokenize_ja_simple():
    t = 'これはテストです。まじやばい！'
    toks = tokenize_ja_simple(t)
    assert 'まじ' in toks and 'やばい' in toks
    assert 'これ' not in toks  # stopword

def test_extract_features():
    t = 'えっと、まじやばい！それな！うーん、たしかに。'
    feats = extract_features(t)
    assert any(f['t'] == 'まじ' for f in feats['top_tokens'])
    assert any(f['t'] == 'それな' for f in feats['top_bigrams'])
    assert any(f['t'] == 'えっと' for f in feats['filler'])
    assert 'punct' in feats and 'politeness' in feats and 'length' in feats
    # PII除外
    t2 = 'John https://foo.com @bar 12345 田中'
    feats2 = extract_features(t2)
    assert not any('John' in f['t'] for f in feats2['top_tokens'])
    assert not any('田中' in f['t'] for f in feats2['top_tokens'])
