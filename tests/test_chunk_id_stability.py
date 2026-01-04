import hashlib
import pytest

class DummyChunk:
    def __init__(self, text, id=None):
        self.text = text
        self.id = id

def stable_chunk_id(text, idx):
    return hashlib.sha1((text + ":" + str(idx)).encode("utf-8")).hexdigest()[:12]

def test_chunk_id_stability():
    text = "テスト"
    idx = 1
    id1 = stable_chunk_id(text, idx)
    id2 = stable_chunk_id(text, idx)
    assert id1 == id2
    assert id1 == hashlib.sha1((text + ":1").encode("utf-8")).hexdigest()[:12]
    # Changing text or idx changes id
    id3 = stable_chunk_id(text, 2)
    id4 = stable_chunk_id("テスト2", 1)
    assert id1 != id3
    assert id1 != id4
