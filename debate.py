import re

def detect_claim(normalized_text: str) -> bool:
    # Simple patterns for claims
    patterns = [
        r".+は.+だ",
        r"絶対",
        r"間違いない",
    ]
    for pat in patterns:
        if re.search(pat, normalized_text):
            return True
    return False

denylist = ["政治","選挙","宗教","差別","人種","性別","国籍"]

def can_debate(context) -> bool:
    # context: dict with keys: behavior_mode, addressed, response_strength, text, emergency, topic
    if context.get("behavior_mode") != "TALK_PRIMARY":
        return False
    if not (context.get("addressed") or context.get("response_strength") == "high"):
        return False
    if not detect_claim(context.get("text", "")):
        return False
    if context.get("emergency") and context["emergency"].is_active():
        return False
    topic = context.get("topic", "")
    if any(word in topic for word in denylist):
        return False
    return True
