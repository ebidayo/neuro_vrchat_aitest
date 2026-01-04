import pytest
from core.is_source_request import is_source_request

@pytest.mark.parametrize("text,expected", [
    ("ソース教えて", True),
    ("出典は？", True),
    ("引用元は？", True),
    ("どこ情報？", True),
    ("どこから？", True),
    ("元ネタは？", True),
    ("urlは？", True),
    ("source please", True),
    ("linkちょうだい", True),
    ("こんにちは", False),
    ("天気は？", False),
    ("", False),
    (None, False),
])
def test_is_source_request(text, expected):
    assert is_source_request(text) == expected
