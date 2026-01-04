from core.content_item import make_content_id, build_content_item
import types

def test_make_content_id_deterministic():
    id1 = make_content_id("news","TestFeed","http://ex.com/1")
    id2 = make_content_id("news","TestFeed","http://ex.com/1")
    assert id1 == id2
    id3 = make_content_id("news","TestFeed","http://ex.com/2")
    assert id1 != id3

def test_build_content_item_fields():
    item = build_content_item("news","TestFeed","地震速報","http://ex.com/1","地震のニュース",123,124)
    assert item["id"]
    assert item["topic"] == "disaster"
    assert item["confidence"] == 0.7
    assert item["kind"] == "news"
    assert item["source"] == "TestFeed"
    assert item["published_ts"] == 123
    assert item["fetched_ts"] == 124

def test_build_content_item_topic_fallback(monkeypatch):
    import core.content_item as ci
    def raise_exc(*a,**k):
        raise Exception("fail")
    monkeypatch.setattr(ci.topic_classifier, "classify_topic", raise_exc)
    item = ci.build_content_item("news","TestFeed","地震速報","http://ex.com/1","地震のニュース",123,124)
    assert item["topic"] == "other"
