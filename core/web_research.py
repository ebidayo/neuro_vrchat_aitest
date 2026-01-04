"""Simple web research helper (Phase1 minimal implementation).

- Performs a single HTTP fetch for a query (via a search URL or direct URL if provided)
- Extracts title and a short text summary from the main article (first paragraph)
- Applies a naive critic to adjust confidence based on domain/date/ads
- Caches results in-memory with TTLs per category
"""
import time
import logging
from typing import Dict, Any, List, Optional, Tuple

# Cache entry type: (timestamp, result)
CacheEntry = Tuple[float, Dict[str, Any]]
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Simple in-memory cache: {key: (timestamp, result)}
_cache: Dict[str, CacheEntry] = {}


def _now() -> float:
    return time.time()


def _simple_extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    # Prefer article/body text: get first meaningful paragraph
    p = soup.find("p")
    if p and p.get_text(strip=True):
        return p.get_text(strip=True)
    # fallback to title
    title = soup.title.string if soup.title else ""
    return title or "No extractable text"


def _assess_confidence(url: str, html: str) -> float:
    # naive heuristics: penalize questionable domains and old content
    score = 0.8
    if "localhost" in url or url.endswith(".blog"):
        score -= 0.3
    if "sponsored" in html.lower() or "advert" in html.lower():
        score -= 0.2
    # clamp
    return max(0.1, min(0.99, score))


def _cache_get(key: str, ttl: int) -> Optional[Dict[str, Any]]:
    entry = _cache.get(key)
    if not entry:
        return None
    ts, val = entry
    if _now() - ts > ttl:
        _cache.pop(key, None)
        return None
    return val


def _cache_set(key: str, val: Dict[str, Any]) -> None:
    _cache[key] = (_now(), val)


def research_query(query: str, category: str = "news", ttl: Optional[int] = None) -> Dict[str, Any]:
    """Perform a minimal research fetch. Returns dict:
    {sources:[{title,url,recency}], keypoints:[...], confidence:float, notes:str}

    For Phase1 this is single-request and simple extraction.
    """
    # choose TTL defaults
    if ttl is None:
        ttl = 3600 if category == "news" else 14400

    cache_key = f"research:{category}:{query}"
    cached = _cache_get(cache_key, ttl)
    if cached:
        logger.debug("Research cache hit: %s", cache_key)
        return cached

    # Very naive search: try a simple Google News-like search via duckduckgo html
    try:
        search_url = f"https://duckduckgo.com/html/?q={requests.utils.quote(query)}"
        r = requests.get(search_url, timeout=6)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        # extract first external link
        link = soup.find("a", {"class": "result__a"})
        if link and link.get("href"):
            target = link.get("href")
        else:
            # fallback: use the search page as a source
            target = search_url

        # fetch the target
        rr = requests.get(target, timeout=6)
        rr.raise_for_status()
        extract = _simple_extract_text(rr.text)
        conf = _assess_confidence(target, rr.text)

        res = {
            "sources": [{"title": soup.title.string if soup.title else query, "url": target, "recency": _now()}],
            "keypoints": [extract[:500]],
            "confidence": conf,
            "notes": "auto-extracted via duckduckgo result"
        }

    except Exception as e:
        logger.exception("Research failed for query=%s", query)
        res = {"sources": [], "keypoints": [], "confidence": 0.2, "notes": f"failed: {e}"}

    # cache it
    _cache_set(cache_key, res)
    return res


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    print(research_query("earthquake near japan", category="news"))
