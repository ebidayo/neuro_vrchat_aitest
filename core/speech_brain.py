"""Speech plan generator with lightweight Neuro-style expressive injections.

This patch keeps the public return shape ({'chunks':..., 'speech_plan':...}) but adds
injected chunk types (think, aside, self_correct, pause, breath, disclaimer) based on
small probabilistic rules driven by scalar inputs.
"""
import math
import random
import logging
import re
from typing import List, Dict, Optional

from .speech_style import (
    compute_injection_probs,
    think_templates,
    aside_templates,
    self_correct_templates,
    breath_templates,
    short_ack_templates,
    adjust_osc_for_type,
)

logger = logging.getLogger(__name__)

MIN_CHUNKS = 1
MAX_CHUNKS = 8
MIN_PAUSE = 80
MAX_PAUSE = 450


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _split_text_fragments(text: str, max_chars: int = 25, rng: random.Random = random.Random()) -> List[str]:
    # First split on sentence-ending punctuation (Japanese and common marks)
    parts = re.split(r'(?<=[。！？.!?])\s*', text.strip())
    fragments: List[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # If the part is short enough, keep
        if len(p) <= max_chars:
            fragments.append(p)
            continue
        # else break into subfragments at spaces or by char count
        words = p.split()
        if len(words) > 1:
            cur = []
            cur_len = 0
            for w in words:
                if cur_len + len(w) + (1 if cur_len > 0 else 0) > max_chars and cur:
                    fragments.append(" ".join(cur))
                    cur = [w]
                    cur_len = len(w)
                else:
                    cur.append(w)
                    cur_len += len(w) + (1 if cur_len > 0 else 0)
            if cur:
                fragments.append(" ".join(cur))
        else:
            # break long string into fixed-size slices, trying to keep words intact isn't possible
            i = 0
            while i < len(p):
                j = min(len(p), i + max_chars)
                fragments.append(p[i:j])
                i = j
    # Merge if we have too many very short fragments
    merged: List[str] = []
    for f in fragments:
        if merged and len(merged[-1]) + len(f) + 1 <= max_chars and rng.random() < 0.2:
            merged[-1] = merged[-1] + " " + f
        else:
            merged.append(f)
    return merged


def make_speech_plan(
    reply: str,
    glitch: float = 0.0,
    curiosity: float = 0.0,
    confidence: float = 0.8,
    social_pressure: float = 0.0,
    arousal: float = 0.1,
    valence: float = 0.0,
    seed: Optional[int] = None,
    use_agents: bool = True,
    agent_pipeline: "AgentPipeline" = None,
) -> Dict:
    """Return an enriched speech plan.

    Keeps compatibility with older callers by returning {'chunks': [...], 'speech_plan': [...]}.

    Added parameters: social_pressure, arousal, valence, seed (deterministic RNG for tests).
    If `use_agents` is True and `agent_pipeline` is provided, attempt to generate via the
    Planner->Critic->Finalizer pipeline. On any failure, fall back to legacy single-shot generation.
    """
    # Agent pipeline short-circuit
    if use_agents and agent_pipeline is not None:
        try:
            # pass scalars and limits to the pipeline so Planner/Critic/Finalizer can use them
            limits = {"max_tokens": 220, "target_chunks": [MIN_CHUNKS, MAX_CHUNKS], "max_chars_per_chunk": 28}
            scalars = {"confidence": confidence, "curiosity": curiosity, "arousal": arousal}
            res = agent_pipeline.generate(state="TALK", user_text=reply, context={}, limits=limits, scalars=scalars)
            if res.get("ok"):
                speech_plan = res.get("speech_plan") or []
                # provide minimal 'chunks' view for backward compatibility
                numeric_chunks: List[Dict] = []
                for c in speech_plan:
                    numeric_chunks.append({
                        "text": c.get("text", ""),
                        "pause_ms": int(c.get("pause_ms", 120)),
                        "type": c.get("type", "say"),
                        "osc": c.get("osc", {}),
                        "confidence_tag": c.get("confidence_tag", "med"),
                    })
                return {"chunks": numeric_chunks, "speech_plan": speech_plan}
        except Exception:
            logger.exception("Agent pipeline failed; falling back to legacy make_speech_plan")

    rng = random.Random(seed)
    text = (reply or "").strip()
    if not text:
        return {"chunks": [], "speech_plan": []}

    # split to base fragments
    frags = _split_text_fragments(text, max_chars=25, rng=rng)
    # limit total fragments
    if len(frags) > MAX_CHUNKS:
        frags = frags[:MAX_CHUNKS]

    probs = compute_injection_probs(glitch=glitch, confidence=confidence, curiosity=curiosity, social_pressure=social_pressure, arousal=arousal)

    chunks: List[Dict] = []

    def _mk_chunk(typ: str, txt: str, pause_ms: int, osc_overrides: Dict = None, confidence_tag: str = "med") -> None:
        # base numeric expressive values
        gesture = _clamp(0.1 + curiosity * 0.6 + rng.random() * 0.3 + (glitch * rng.random() * 0.5), 0.0, 1.0)
        look = _clamp(0.5 + (rng.uniform(-0.25, 0.25)), 0.0, 1.0)
        a = _clamp(arousal + rng.random() * 0.15, 0.0, 1.0)
        v = _clamp(valence + (rng.random() - 0.5) * 0.2, -1.0, 1.0)
        osc = {"N_State": "TALK", "N_Arousal": float(round(a, 3)), "N_Valence": float(round(v, 3)), "N_Gesture": float(round(gesture, 3)), "N_Look": float(round(look, 3))}
        if osc_overrides:
            osc.update(osc_overrides)
        osc = adjust_osc_for_type(osc, typ, a, v)
        chunks.append({
            "type": typ,
            "text": txt,
            "pause_ms": int(pause_ms),
            "osc": osc,
            "confidence_tag": confidence_tag,
        })

    # build sequence with possible injections
    for i, f in enumerate(frags):
        # sometimes prepend a short think/aside
        if rng.random() < probs["p_think"]:
            _mk_chunk("think", rng.choice(think_templates), pause_ms=rng.randint(120, 280), confidence_tag=("low" if confidence < 0.45 else "med"))
        elif rng.random() < probs["p_aside"]:
            _mk_chunk("aside", rng.choice(aside_templates), pause_ms=rng.randint(120, 240), confidence_tag=("low" if confidence < 0.45 else "med"))

        # main fragment
        _mk_chunk("say", f, pause_ms=rng.randint(80, 220), confidence_tag=("low" if confidence < 0.45 else "med"))

        # injection after fragment
        if rng.random() < probs["p_self_correct"]:
            _mk_chunk("self_correct", rng.choice(self_correct_templates), pause_ms=rng.randint(80, 200), confidence_tag=("low" if confidence < 0.45 else "med"))
        if rng.random() < probs["p_pause"]:
            _mk_chunk("pause", "", pause_ms=rng.randint(150, 450), confidence_tag="med")
        if rng.random() < probs["p_breath"]:
            _mk_chunk("breath", rng.choice(breath_templates), pause_ms=rng.randint(80, 160), confidence_tag="med")

    # mandatory disclaimer for low confidence
    if probs.get("must_disclaimer"):
        _mk_chunk("disclaimer", rng.choice(["確信はない。", "間違ってたらごめん。", "これは推測。"]), pause_ms=rng.randint(160, 240), confidence_tag="low")

    # ensure at least one self_correct if required
    if probs.get("must_self_correct") and not any(c["type"] == "self_correct" for c in chunks):
        # insert before last say or at end
        idx = len(chunks) - 1
        if idx >= 0:
            chunks.insert(idx, {"type": "self_correct", "text": rng.choice(self_correct_templates), "pause_ms": rng.randint(80, 200), "osc": {}, "confidence_tag": "low"})
        else:
            _mk_chunk("self_correct", rng.choice(self_correct_templates), pause_ms=rng.randint(80, 200), confidence_tag="low")

    # social pressure -> extra short ack
    if social_pressure > 0.75:
        _mk_chunk("aside", rng.choice(short_ack_templates), pause_ms=rng.randint(80, 140), confidence_tag="med")

    # Build v1.2 speech_plan list with ids and ensure each chunk has an osc map
    speech_plan: List[Dict] = []
    for i, c in enumerate(chunks, start=1):
        osc = c.get("osc") or {"N_State": "TALK", "N_Arousal": float(_clamp(arousal, 0.0, 1.0)), "N_Valence": float(_clamp(valence, -1.0, 1.0)), "N_Gesture": 0.3, "N_Look": 0.5}
        # ensure ranges
        osc["N_Arousal"] = float(_clamp(osc.get("N_Arousal", 0.0), 0.0, 1.0))
        osc["N_Valence"] = float(_clamp(osc.get("N_Valence", 0.0), -1.0, 1.0))
        osc["N_Gesture"] = float(_clamp(osc.get("N_Gesture", 0.0), 0.0, 1.0))
        osc["N_Look"] = float(_clamp(osc.get("N_Look", 0.0), 0.0, 1.0))

        speech_plan.append({
            "id": f"c{i}",
            "type": c.get("type", "say"),
            "text": c.get("text", ""),
            "pause_ms": int(c.get("pause_ms", MIN_PAUSE)),
            "osc": osc,
            "confidence_tag": c.get("confidence_tag", "med"),
        })

    # also return numeric 'chunks' mapping for backward compatibility (simple view)
    numeric_chunks: List[Dict] = []
    for c in speech_plan:
        numeric_chunks.append({
            "text": c.get("text", ""),
            "pause_ms": c.get("pause_ms", MIN_PAUSE),
            "type": c.get("type", "say"),
            "osc": c.get("osc", {}),
            "confidence_tag": c.get("confidence_tag", "med"),
        })

    plan = {"chunks": numeric_chunks, "speech_plan": speech_plan}
    logger.debug("Enhanced speech plan generated (confidence=%.2f): %s", confidence, plan)
    return plan


# ---- SEARCH-specific plan builders ----

def build_search_intro_plan(glitch: float = 0.0, curiosity: float = 0.0, confidence: float = 0.8, seed: Optional[int] = None) -> Dict:
    rng = random.Random(seed)
    chunks: List[Dict] = []
    # short think + pause + aside
    # intro chunk: focused SEARCH gaze, higher arousal to convey urgency
    na_intro = max(0.65, _clamp(0.15 + (curiosity * 0.2), 0.0, 1.0))
    chunks.append({
        "id": "s1",
        "type": "think",
        "text": "…調べる。",
        "pause_ms": rng.randint(120, 220),
        "osc": {"N_State": "SEARCH", "N_Arousal": float(round(na_intro, 3)), "N_Valence": _clamp(-0.05, -1.0, 1.0), "N_Gesture": 0.2, "N_Look": 0.98},
    })
    chunks.append({
        "id": "s2",
        "type": "aside",
        "text": "ちょっと待って。",
        "pause_ms": rng.randint(140, 260),
        "osc": {"N_State": "SEARCH", "N_Arousal": _clamp(0.2 + (curiosity * 0.15), 0.0, 1.0), "N_Valence": _clamp(-0.05, -1.0, 1.0), "N_Gesture": 0.25, "N_Look": 0.98},
    })
    plan = {"speech_plan": chunks, "chunks": chunks}
    return plan


def build_search_thinking_loop_plan(step: int = 0, seed: Optional[int] = None) -> Dict:
    rng = random.Random(seed)
    texts = ["んー…", "どこだったっけ", "出てきて…"]
    t = texts[step % len(texts)]
    chunk = {"id": f"t{step}", "type": "think", "text": t, "pause_ms": rng.randint(120, 280), "osc": {"N_State": "SEARCH", "N_Arousal": 0.55, "N_Valence": -0.05, "N_Gesture": 0.2, "N_Look": 0.98}}
    return {"speech_plan": [chunk], "chunks": [chunk]}


def build_search_result_plan(result: Dict, seed: Optional[int] = None) -> Dict:
    """Produce a structured 'result plan' with 3 bullets, explanation, follow-up question, and disclaimer as needed.

    Follows the spec: intro, 3 bullets, explanation (one-liner), follow-up question, optional disclaimer.
    """
    rng = random.Random(seed)
    chunks: List[Dict] = []
    res = result or {}
    items = res.get("items", []) or []
    query = (res.get("query") or "")

    # Helper to make a safe bullet from an item
    def _make_bullet_text(it: Dict) -> str:
        text = (it.get("summary") or it.get("title") or "情報が見つかりました").strip()
        # remove leading symbols/spaces and newlines
        text = text.lstrip("\n\r .、。,・-–—#*[]()")
        text = text.replace("\n", " ").replace("\r", " ")
        # take first sentence up to punctuation
        import re
        m = re.split(r'[。.!?]', text)
        if m and m[0].strip():
            text = m[0].strip()
        # truncate if too long
        if len(text) > 35:
            text = text[:32].rstrip() + "…"
        return text

    seen = set()
    bullets: List[str] = []
    for it in items:
        b = _make_bullet_text(it)
        if b and b not in seen:
            bullets.append(b)
            seen.add(b)
        if len(bullets) >= 3:
            break

    # if not enough bullets, pad
    if len(bullets) < 3:
        # use what's available and pad with a general note
        while len(bullets) < 3:
            if len(items) >= len(bullets) + 1:
                # nothing to do, we already added
                break
            bullets.append("関連情報は更新されやすいです")

    # (0) intro
    chunks.append({
        "id": "r0",
        "type": "say",
        "text": f"要点、3つ。",
        "pause_ms": rng.randint(140, 220),
        "osc": {"N_State": "TALK", "N_Arousal": 0.55, "N_Valence": _clamp(0.0, -1.0, 1.0), "N_Gesture": 0.2, "N_Look": 0.9},
    })

    # (1) bullets
    for i in range(3):
        text = bullets[i] if i < len(bullets) else "関連情報は更新されやすいです"
        chunks.append({
            "id": f"r{i+1}",
            "type": "say",
            "text": f"{i+1}) {text}。",
            "pause_ms": 140,
            "osc": {"N_State": "TALK", "N_Arousal": 0.5, "N_Valence": 0.0, "N_Gesture": 0.2, "N_Look": 0.85},
        })

    # (2) explanation: build one-liner
    def _extract_topic(bullets_list: List[str]) -> str:
        # naive ngram frequency for n=2..4
        from collections import Counter
        candidates = Counter()
        for b in bullets_list:
            s = b
            # collect substrings length 2..4
            for n in range(2, 5):
                for i in range(0, max(0, len(s) - n + 1)):
                    ngram = s[i:i+n]
                    candidates[ngram] += 1
        # choose the most common ngram that appears in at least 2 bullets
        for ng, cnt in candidates.most_common():
            if cnt >= 2 and len(ng.strip()) >= 2:
                return ng
        return ""

    topic = _extract_topic(bullets)
    if topic:
        one_liner = f"{topic}の話で、今は要点だけ押さえればOK。"
    else:
        one_liner = f"{bullets[0]}って感じ。"

    chunks.append({"id": "rX", "type": "aside", "text": "ざっくり言うと…", "pause_ms": 160, "osc": {"N_State": "TALK", "N_Arousal": 0.5, "N_Valence": -0.02, "N_Gesture": 0.2, "N_Look": 0.9}})
    chunks.append({"id": "rY", "type": "say", "text": f"つまり {one_liner}", "pause_ms": 160, "osc": {"N_State": "TALK", "N_Arousal": 0.5, "N_Valence": -0.01, "N_Gesture": 0.2, "N_Look": 0.9}})

    # (3) follow-up question (one only)
    q = "目的は“ざっくり”か“細かく”どっちがいい？"
    q_low = query.lower()
    if not any(k in q_low for k in ["いつ", "今日", "今", "最新", "recent"]):
        q = "いつ時点の話がいい？"
    elif not any(k in q_low for k in ["地域", "どこ", "都", "県", "市"]):
        q = "どの地域の話？"
    chunks.append({"id": "rQ", "type": "say", "text": f"確認。{q}", "pause_ms": 160, "osc": {"N_State": "TALK", "N_Arousal": 0.45, "N_Valence": 0.0, "N_Gesture": 0.2, "N_Look": 0.9}})

    # (4) disclaimer if needed
    conf = res.get("confidence")
    if conf is not None and conf < 0.55 or len(items) < 3:
        disc_text = "状況で変わるかも。必要なら追い調べします。"
        chunks.append({"id": "rZ", "type": "disclaimer", "text": disc_text, "pause_ms": 180, "osc": {"N_State": "TALK", "N_Arousal": 0.28, "N_Valence": -0.05, "N_Gesture": 0.15, "N_Look": 0.9}})

    return {"speech_plan": chunks, "chunks": chunks}


def build_search_fail_plan(error: str = "", seed: Optional[int] = None) -> Dict:
    rng = random.Random(seed)
    chunks: List[Dict] = []
    chunks.append({"id": "f1", "type": "self_correct", "text": "…あ、ごめん。取れない。", "pause_ms": 120, "osc": {"N_State": "SEARCH", "N_Arousal": 0.3, "N_Valence": -0.1, "N_Gesture": 0.25, "N_Look": 0.95}})
    chunks.append({"id": "f2", "type": "say", "text": "通信かもしれません。", "pause_ms": 140, "osc": {"N_State": "SEARCH", "N_Arousal": 0.28, "N_Valence": -0.08, "N_Gesture": 0.2, "N_Look": 0.95}})
    chunks.append({"id": "f3", "type": "say", "text": "あとでもう一回やってみます。", "pause_ms": 140, "osc": {"N_State": "SEARCH", "N_Arousal": 0.26, "N_Valence": -0.07, "N_Gesture": 0.18, "N_Look": 0.95}})
    chunks.append({"id": "f4", "type": "disclaimer", "text": "今は推測で断定しません。", "pause_ms": 160, "osc": {"N_State": "SEARCH", "N_Arousal": 0.2, "N_Valence": -0.05, "N_Gesture": 0.15, "N_Look": 0.95}})
    return {"speech_plan": chunks, "chunks": chunks}



# ---- IDLE / starter plan helpers ----

def build_idle_presence_plan(scalars: Dict[str, float]) -> Dict:
    """Return a single-chunk plan for idle presence (very short, unobtrusive)."""
    rng = random.Random(int(scalars.get("seed", 0)) if scalars else None)
    kind = scalars.get("kind") or "think"
    if kind == "aside":
        text = scalars.get("text", "んー。")
        typ = "aside"
    elif kind == "self_correct":
        text = scalars.get("text", "あ、いや。")
        typ = "self_correct"
    elif kind == "pause":
        text = ""
        typ = "pause"
    else:
        text = scalars.get("text", "…")
        typ = "think"

    a = float(scalars.get("arousal", 0.3))
    look = float(scalars.get("look", 0.5))
    osc = {"N_State": "IDLE", "N_Arousal": a, "N_Valence": float(scalars.get("valence", 0.0)), "N_Gesture": float(scalars.get("gesture", 0.12)), "N_Look": look}
    chunk = {"id": "idle1", "type": typ, "text": text, "pause_ms": int(scalars.get("pause_ms", 120)), "osc": osc}
    return {"speech_plan": [chunk], "chunks": [chunk]}


def build_starter_plan(scalars: Dict[str, float]) -> Dict:
    """Return a single-chunk starter plan (short question / invitation to talk)."""
    txt = str(scalars.get("text", "ねえ。"))
    # clamp length
    if len(txt) > 16:
        txt = txt[:15].rstrip() + "…"
    osc = {"N_State": "TALK", "N_Arousal": float(scalars.get("arousal", 0.5)), "N_Valence": float(scalars.get("valence", 0.0)), "N_Gesture": float(scalars.get("gesture", 0.18)), "N_Look": float(scalars.get("look", 0.8))}
    typ = "question" if txt.endswith("？") or txt.endswith("?") else "say"
    chunk = {"id": "starter1", "type": typ, "text": txt, "pause_ms": int(scalars.get("pause_ms", 120)), "osc": osc}
    return {"speech_plan": [chunk], "chunks": [chunk]}


# ---- Name-ask plan helpers (single-chunk, short) ----

def build_name_ask_plan(alias: str, scalars: Dict[str, float]) -> Dict:
    """One-chunk plan to ask a name for alias (friendly, short)."""
    txt = scalars.get("text") or "ねえ、呼び方どうしよう。名前、教えて？"
    txt = str(txt)[:32]
    osc = {"N_State": "TALK", "N_Arousal": float(scalars.get("arousal", 0.45)), "N_Valence": float(scalars.get("valence", 0.05)), "N_Gesture": float(scalars.get("gesture", 0.18)), "N_Look": float(scalars.get("look", 0.8))}
    chunk = {"id": f"name_ask_{alias}", "type": "question", "text": txt, "pause_ms": int(scalars.get("pause_ms", 140)), "osc": osc}
    return {"speech_plan": [chunk], "chunks": [chunk]}


def build_name_confirm_plan(name: str, scalars: Dict[str, float]) -> Dict:
    """Confirm the candidate name and ask for consent to remember it."""
    txt = f"{name}…で合ってる？覚えていい？"
    txt = str(txt)[:40]
    osc = {"N_State": "TALK", "N_Arousal": float(scalars.get("arousal", 0.55)), "N_Valence": float(scalars.get("valence", 0.05)), "N_Gesture": float(scalars.get("gesture", 0.18)), "N_Look": float(scalars.get("look", 0.75))}
    chunk = {"id": f"name_confirm_{name}", "type": "question", "text": txt, "pause_ms": int(scalars.get("pause_ms", 140)), "osc": osc}
    return {"speech_plan": [chunk], "chunks": [chunk]}


def build_name_saved_plan(name: str, scalars: Dict[str, float]) -> Dict:
    txt = f"了解、{name}ね。覚えた。"
    txt = str(txt)[:40]
    osc = {"N_State": "TALK", "N_Arousal": float(scalars.get("arousal", 0.35)), "N_Valence": float(scalars.get("valence", 0.1)), "N_Gesture": float(scalars.get("gesture", 0.12)), "N_Look": float(scalars.get("look", 0.6))}
    chunk = {"id": f"name_saved_{name}", "type": "say", "text": txt, "pause_ms": int(scalars.get("pause_ms", 120)), "osc": osc}
    return {"speech_plan": [chunk], "chunks": [chunk]}


def build_name_retry_plan(scalars: Dict[str, float]) -> Dict:
    txt = scalars.get("text") or "ごめん、もう一回名前だけ言って。"
    txt = str(txt)[:40]
    osc = {"N_State": "TALK", "N_Arousal": float(scalars.get("arousal", 0.4)), "N_Valence": float(scalars.get("valence", 0.0)), "N_Gesture": float(scalars.get("gesture", 0.12)), "N_Look": float(scalars.get("look", 0.6))}
    chunk = {"id": "name_retry", "type": "question", "text": txt, "pause_ms": int(scalars.get("pause_ms", 140)), "osc": osc}
    return {"speech_plan": [chunk], "chunks": [chunk]}


def build_forget_ack_plan(name: str, scalars: Dict[str, float]) -> Dict:
    txt = f"OK、{name}の記憶を消した。"
    txt = str(txt)[:40]
    osc = {"N_State": "TALK", "N_Arousal": float(scalars.get("arousal", 0.25)), "N_Valence": float(scalars.get("valence", 0.0)), "N_Gesture": float(scalars.get("gesture", 0.12)), "N_Look": float(scalars.get("look", 0.5))}
    chunk = {"id": f"forget_ack_{name}", "type": "say", "text": txt, "pause_ms": int(scalars.get("pause_ms", 120)), "osc": osc}
    return {"speech_plan": [chunk], "chunks": [chunk]}


# ---- GREET plan helper ----

def build_greet_plan(name: str, greet_type: str | None = None, scalars: Dict[str, float] = None) -> Dict:
    """Return a single-chunk greet plan addressing the given name."""
    if scalars is None:
        scalars = {}
    gt = greet_type or scalars.get("greet_type") or "day"
    if gt == "morning":
        txt = f"おはよ、{name}。"
    elif gt == "night":
        txt = f"こんばんは、{name}。"
    else:
        txt = f"や、{name}。"
    txt = str(txt)[:20]
    a = float(scalars.get("arousal", 0.5))
    val = float(scalars.get("valence", 0.15))
    osc = {"N_State": "GREET", "N_Arousal": a, "N_Valence": val, "N_Gesture": float(scalars.get("gesture", 0.12)), "N_Look": float(scalars.get("look", 0.85))}
    chunk = {"id": f"greet_{name}", "type": "say", "text": txt, "pause_ms": int(scalars.get("pause_ms", 120)), "osc": osc}
    return {"speech_plan": [chunk], "chunks": [chunk]}


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    text = "今日はいい天気ですね。散歩に行きましょう。"
    print(make_speech_plan(text, glitch=0.6, curiosity=0.2, confidence=0.4, social_pressure=0.8, seed=42))
