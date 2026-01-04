import pytest
from debate_structure import build_debate_response

def test_build_debate_response_structure():
    claim = "寿司は最高"
    counter = "健康面"
    chunks = build_debate_response(claim, counter)
    assert isinstance(chunks, list)
    assert len(chunks) == 3
    assert "前提" in chunks[0]
    assert "説明" in chunks[1]
    assert "成り立たない" in chunks[2]
    # Order preserved
    assert chunks[0].startswith("なるほど")
    assert chunks[2].startswith("だから")
