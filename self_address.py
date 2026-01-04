from dataclasses import dataclass
from typing import List

def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))

def _contains_any(text: str, needles: List[str]) -> bool:
    return any(n in text for n in needles if n)

def normalize_text(text: str) -> str:
    t = text.strip()
    t = t.replace('　', ' ')  # full-width space to ascii
    t = t.replace('？', '?')  # full-width question to ascii
    t = t.replace('！', '!')  # full-width exclam to ascii
    t = t.lower()
    t = ' '.join(t.split())  # collapse whitespace
    return t

def build_name_aliases(raw_aliases: List[str]) -> List[str]:
    seen = set()
    out = []
    for a in raw_aliases:
        a = a.strip()
        if a and a not in seen:
            seen.add(a)
            out.append(a)
    return out

@dataclass(frozen=True)
class AddressDecision:
    addressed: bool
    score: float
    reason: str

def detect_self_address(text: str, *, name_aliases: List[str], enable_debug_reason: bool = True, confirmed_aliases: list = None) -> AddressDecision:
    t = normalize_text(text)
    score = 0.0
    reason_parts = []
    aliases = build_name_aliases(name_aliases)
    if _contains_any(t, aliases):
        score += 0.6
        if enable_debug_reason:
            reason_parts.append('name')
    # PR2.5: confirmed learned aliases (soft boost)
    if confirmed_aliases:
        confirmed_aliases = build_name_aliases(confirmed_aliases)
        if _contains_any(t, confirmed_aliases):
            score += 0.4
            if enable_debug_reason:
                reason_parts.append('confirmed')
    req_patterns = ["して", "お願い", "教えて", "聞いて"]
    if _contains_any(t, req_patterns):
        score += 0.2
        if enable_debug_reason:
            reason_parts.append('req')
    q_patterns = ["?", "何", "どれ", "どう"]
    if _contains_any(t, q_patterns):
        score += 0.2
        if enable_debug_reason:
            reason_parts.append('q')
    third_person = ["あいつ", "彼", "彼女", "って言ってた"]
    if _contains_any(t, third_person):
        score -= 0.5
        if enable_debug_reason:
            reason_parts.append('-3p')
    score = _clamp01(score)
    score = float(f"{score:.4f}")
    addressed = (score >= 0.6)
    reason = '+'.join(reason_parts) if enable_debug_reason else ''
    return AddressDecision(addressed, score, reason)
