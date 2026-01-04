import hashlib
from core import topic_classifier

def make_content_id(kind: str, source: str, url: str) -> str:
    try:
        s = f"{kind}|{source}|{url}"
        return hashlib.sha1(s.encode("utf-8")).hexdigest()
    except Exception:
        return hashlib.sha1((url or "").encode("utf-8")).hexdigest()

def build_content_item(kind, source, title, url, summary, published_ts, fetched_ts, query=None):
    try:
        topic = topic_classifier.classify_topic(title, summary if summary else (query or ""))
    except Exception:
        topic = "other"
    confidence = 0.7 if kind == "news" else 0.6
    try:
        cid = make_content_id(kind, source, url)
    except Exception:
        cid = hashlib.sha1((url or "").encode("utf-8")).hexdigest()
    item = {
        "kind": kind,
        "id": cid,
        "title": title,
        "url": url,
        "summary": summary,
        "topic": topic,
        "published_ts": int(published_ts or fetched_ts),
        "fetched_ts": int(fetched_ts),
        "confidence": float(confidence),
        "source": source,
    }
    if query is not None:
        item["query"] = query
    return item
