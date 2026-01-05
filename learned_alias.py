def normalize_for_alias(text: str) -> str:
    t = text.strip()
    t = t.replace('　', ' ')
    t = t.lower()
    t = ' '.join(t.split())
    return t

def filter_candidate(alias: str, cfg) -> bool:
    min_len = int(cfg.get("min_len", 2))
    max_len = int(cfg.get("max_len", 8))
    if not (min_len <= len(alias) <= max_len):
        return False
    if any(tok in alias for tok in cfg.get("forbid_tokens", [])):
        return False
    if re.search(r'\s', alias):
        return False
    allow_latin = cfg.get("allow_latin", True)
    allow_kana = cfg.get("allow_kana", True)
    allow_kanji = cfg.get("allow_kanji", False)
    # Latin
    if not allow_latin and re.search(r'[a-z0-9]', alias):
        return False
    # Kana
    if not allow_kana and re.search(r'[\u3040-\u309F\u30A0-\u30FF]', alias):
        return False
    # Kanji
    if not allow_kanji and re.search(r'[\u4E00-\u9FFF]', alias):
        return False
    # Punctuation (except "ー" if kana allowed)
    if allow_kana:
        if re.search(r'[^\w\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFFー]', alias):
            return False
    else:
        if re.search(r'[^\w\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', alias):
            return False
    return True
import re
from typing import List

def extract_candidate_alias(normalized_text: str, min_len=2, max_len=8, forbid_tokens=None, allow_latin=True, allow_kana=True, allow_kanji=False) -> List[str]:
    """
    Deterministically extract candidate aliases from normalized_text.
    Patterns:
      - <alias>って呼んで
      - <alias>でいい
      - <alias>でお願い
      - 呼び方は<alias>
      - あだ名は<alias>
      - <alias>で (if at end or after direct address)
    """
    if forbid_tokens is None:
        forbid_tokens = []
    candidates = set()
    # Patterns (extract first, then length check)
    # 1. <alias>って呼んで
    for m in re.finditer(r'([\w\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]+)って呼んで', normalized_text):
        candidates.add(m.group(1))
    # 2. <alias>でいい
    for m in re.finditer(r'([\w\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]+)でいい', normalized_text):
        candidates.add(m.group(1))
    # 3. <alias>でお願い
    for m in re.finditer(r'([\w\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]+)でお願い', normalized_text):
        candidates.add(m.group(1))
    # 4/5. あだ名は<alias> / 呼び方は<alias> (stop at でお願い, 願い, punctuation, whitespace, or end)
    for m in re.finditer(r'(?:あだ名|呼び方)は\s*([\w\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]+?)(?:でお願い|お願い|ね|よ|$|[。！？\s])', normalized_text):
        candidates.add(m.group(1))
    # 6. <alias>で (at end)
    for m in re.finditer(r'([\w\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]+)で[\s\u3000]*$', normalized_text):
        candidates.add(m.group(1))
    # Filter
    filtered = []
    for alias in sorted(candidates):
        if not (min_len <= len(alias) <= max_len):
            continue
        if any(tok in alias for tok in forbid_tokens):
            continue
        # Charsets
        if not allow_latin and re.search(r'[A-Za-z0-9]', alias):
            continue
        if not allow_kana and re.search(r'[\u3040-\u309F\u30A0-\u30FF]', alias):
            continue
        if not allow_kanji and re.search(r'[\u4E00-\u9FFF]', alias):
            continue
        # No whitespace or most punct
        if re.search(r'[^\w\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', alias):
            continue
        filtered.append(alias)
    return filtered
