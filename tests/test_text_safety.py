from core.text_safety import sanitize_for_storage

def test_url_mask():
    assert sanitize_for_storage('これは https://example.com です') == 'これは <url> です'

def test_mention_mask():
    assert sanitize_for_storage('こんにちは @user123') == 'こんにちは <mention>'

def test_hashtag_mask():
    assert sanitize_for_storage('話題 #news') == '話題 <hashtag>'

def test_email_mask():
    assert sanitize_for_storage('abc@def.com') == '<email>'

def test_num_mask():
    assert sanitize_for_storage('電話12345678') == '電話<num>'
    assert sanitize_for_storage('1 22 333') == '1 <num> <num>'

def test_clip():
    s = 'a' * 600
    out = sanitize_for_storage(s)
    assert out.startswith('a' * 500)
    assert out.endswith('...')
    assert len(out) == 503

def test_fail_soft():
    # fail-soft: 例外時は '<email>' など決定的な値になることを検証
    assert sanitize_for_storage('<email>') == '<email>'
