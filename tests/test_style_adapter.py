import pytest
from core.style_adapter import apply_style

def test_apply_style_basic():
    prof = {
        'top_tokens': [{'t':'まじ','c':5}],
        'top_bigrams': [{'t':'それな','c':3}],
        'filler': [{'t':'えっと','c':2}]
    }
    text = '今日はいい天気だね。'
    out = apply_style(text, prof, {'max_inserts':1, 'allow_filler':True, 'allow_bigram':True, 'allow_token':True})
    assert out != text
    # 既存語は重複しない
    text2 = 'まじ今日はやばい'
    out2 = apply_style(text2, prof, {'max_inserts':1, 'allow_filler':True, 'allow_bigram':True, 'allow_token':True})
    assert out2 == text2 or out2.count('まじ') == 1

def test_apply_style_max_inserts():
    prof = {'top_tokens':[{'t':'やば','c':3}], 'top_bigrams':[{'t':'それな','c':2}], 'filler':[{'t':'うーん','c':1}]}
    text = 'すごいね。'
    out = apply_style(text, prof, {'max_inserts':1, 'allow_filler':True, 'allow_bigram':True, 'allow_token':True})
    assert out.count('やば') + out.count('それな') + out.count('うーん') <= 1

def test_apply_style_no_profile():
    text = '普通の文です。'
    out = apply_style(text, None, {'max_inserts':1})
    assert out == text

def test_apply_style_no_duplicate_question():
    prof = {'top_tokens':[], 'top_bigrams':[], 'filler':[{'t':'えっと','c':2}]}
    text = 'どうしたの？'
    out = apply_style(text, prof, {'max_inserts':1, 'allow_filler':True})
    assert out.count('？') <= 1
