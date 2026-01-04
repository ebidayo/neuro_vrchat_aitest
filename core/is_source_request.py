def is_source_request(text: str) -> bool:
    if not text:
        return False
    t = text.lower()
    triggers = [
        "ソース", "出典", "引用", "どこ情報", "どこから", "元ネタ",
        "url", "source", "link",
    ]
    return any(x in t for x in triggers)