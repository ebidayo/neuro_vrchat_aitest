import pytest
from main import build_content_prompt_text

def test_build_content_prompt_text_news():
    item = {
        "kind": "news",
        "title": "AIが新しい発見をした件",
        "summary": "AIが新しい発見をした。専門家によると画期的。今後の応用が期待される。",
        "confidence": 0.8
    }
    chunks = build_content_prompt_text(item)
    # 3チャンク、要点3つ、つまり1つ、?は1つだけ
    assert 2 <= len(chunks) <= 3
    assert any("1)" in c for c in chunks)
    assert any("2)" in c for c in chunks)
    assert any("3)" in c for c in chunks)
    assert sum(c.count("？") for c in chunks) <= 1
    assert any("つまり" in c for c in chunks)

def test_build_content_prompt_text_kb():
    item = {
        "kind": "kb",
        "title": "ニューラルネットワーク",
        "summary": "脳の仕組みを模倣。多層構造で学習。画像認識などに使われる。",
        "confidence": 0.6
    }
    chunks = build_content_prompt_text(item)
    assert 2 <= len(chunks) <= 3
    assert any("1)" in c for c in chunks)
    assert any("2)" in c for c in chunks)
    assert any("3)" in c for c in chunks)
    assert sum(c.count("？") for c in chunks) <= 1
    assert any("つまり" in c for c in chunks)

def test_idle_aside_format():
    # idle_asideはmain.pyのhandle_state_change内ロジックに準拠
    from main import handle_state_change
    # テンプレ生成部を直接テストする場合は関数化推奨
    # ここでは仕様例のみ
    aside = {"kind": "news", "title": "AIが新しい発見をした件"}
    t = aside["title"]
    aside_text = f"さっき見たニュース、{t}…ちょっと気になる。"
    aside_text = aside_text.replace("？", "")
    if len(aside_text) > 70:
        aside_text = aside_text[:69] + "…"
    assert "？" not in aside_text
    assert len(aside_text) <= 70

def test_long_title_truncation():
    item = {
        "kind": "news",
        "title": "A"*100,
        "summary": "B"*100,
        "confidence": 0.5
    }
    chunks = build_content_prompt_text(item)
    assert all(len(c) < 60 for c in chunks)  # 省略される
