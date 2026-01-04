"""Speech style utilities and small probabilistic model for Neuro-like hesitations.

Provides templates and probability computations and small OSC adjustments per chunk type.
"""
from typing import Dict, List


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


think_templates: List[str] = [
    "んー…",
    "ちょっと考える。",
    "いまの、気になる。",
    "待って、整理する。",
]

aside_templates: List[str] = [
    "小声だけど…",
    "これ、内緒ね。",
    "たぶん、だけど。",
]

self_correct_templates: List[str] = [
    "…いや、違う。",
    "まって、言い方変える。",
    "ごめん、いったん戻す。",
]

breath_templates: List[str] = [
    "…ふっ",
    "…すぅ",
    "…ん",
]

short_ack_templates: List[str] = [
    "えっと",
    "うん",
    "そうですね",
]


def compute_injection_probs(glitch: float, confidence: float, curiosity: float, social_pressure: float, arousal: float) -> Dict[str, float]:
    """Compute injection probabilities from scalar inputs.

    Returns dict with probabilities for think, aside, self_correct, pause, breath and flags for mandatory insertion.
    """
    p_think = _clamp(0.08 + 0.25 * curiosity + 0.10 * glitch, 0.0, 0.45)
    p_aside = _clamp(0.05 + 0.20 * glitch + 0.10 * (1.0 - confidence), 0.0, 0.40)
    p_self_correct = _clamp(0.03 + 0.30 * glitch + 0.15 * (1.0 - confidence), 0.0, 0.55)
    p_pause = _clamp(0.08 + 0.25 * glitch + 0.10 * social_pressure, 0.0, 0.60)
    p_breath = _clamp(0.02 + 0.10 * arousal + 0.10 * social_pressure, 0.0, 0.25)

    must_self_correct = glitch > 0.6
    must_disclaimer = confidence < 0.45

    return {
        "p_think": p_think,
        "p_aside": p_aside,
        "p_self_correct": p_self_correct,
        "p_pause": p_pause,
        "p_breath": p_breath,
        "must_self_correct": must_self_correct,
        "must_disclaimer": must_disclaimer,
    }


def adjust_osc_for_type(base_osc: Dict[str, float], typ: str, arousal: float, valence: float) -> Dict[str, float]:
    """Return a shallow-copied osc dict adjusted slightly based on chunk type.

    Keeps values clamped to sensible ranges.
    """
    def _cl(v, lo, hi):
        return max(lo, min(hi, v))

    osc = dict(base_osc or {})
    # ensure base keys
    osc.setdefault("N_State", "TALK")
    osc.setdefault("N_Arousal", float(_cl(arousal, 0.0, 1.0)))
    osc.setdefault("N_Valence", float(_cl(valence, -1.0, 1.0)))
    osc.setdefault("N_Gesture", float(_cl(0.3, 0.0, 1.0)))
    osc.setdefault("N_Look", float(_cl(0.5, 0.0, 1.0)))

    if typ == "think":
        osc["N_Look"] = _cl(osc.get("N_Look", 0.5) + 0.10, 0.0, 1.0)
    elif typ == "aside":
        osc["N_Look"] = _cl(osc.get("N_Look", 0.5) - 0.05, 0.0, 1.0)
        osc["N_Gesture"] = _cl(osc.get("N_Gesture", 0.3) * 0.9, 0.0, 1.0)
    elif typ == "self_correct":
        osc["N_Gesture"] = _cl(osc.get("N_Gesture", 0.3) + 0.10, 0.0, 1.0)
    elif typ == "pause":
        osc["N_Gesture"] = _cl(osc.get("N_Gesture", 0.3) * 0.6, 0.0, 1.0)
    elif typ == "breath":
        osc["N_Gesture"] = _cl(osc.get("N_Gesture", 0.3) * 0.4, 0.0, 1.0)

    return osc
