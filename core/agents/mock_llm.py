"""A minimal mock LLM that implements the JSON I/O described in the spec.

It has deterministic, fast behavior suitable for tests (no network, no heavy deps).
"""
from typing import Any, Dict, List, Optional


def call_llm(payload: Dict[str, Any]) -> Dict[str, Any]:
    role = payload.get("role")
    if role == "planner":
        return _planner_mock(payload)
    if role == "critic":
        return _critic_mock(payload)
    if role == "finalizer":
        return _finalizer_mock(payload)
    return {"ok": False, "error": "unknown role"}


def _planner_mock(payload: Dict[str, Any]) -> Dict[str, Any]:
    # Create a short draft: 3 key points and a follow-up question; respect limits.target_chunks
    limits = payload.get("limits", {}) or {}
    target = limits.get("target_chunks", [1, 3])
    max_chunks = target[1] if isinstance(target, (list, tuple)) and len(target) >= 2 else 3
    user_text = payload.get("user_text", "") or ""

    # create short key_points based on user_text tokens
    tokens = [t for t in user_text.split() if t]
    key_points = [f"要点{i+1}: {tokens[i] if i < len(tokens) else '情報'}" for i in range(min(3, max_chunks))]

    content: List[Dict[str, str]] = []
    for i, kp in enumerate(key_points):
        content.append({"type": "say", "text": kp})

    # always add exactly one question at the end
    question = {"type": "say", "text": "ざっくりでいいですか？"}

    if len(content) < max_chunks:
        content.append(question)
    else:
        # replace last with question to ensure a follow-up exists
        content[-1] = question

    draft = {
        "intent": "answer",
        "key_points": key_points,
        "tone": {"polite": 0.2, "teasing": 0.1, "serious": 0.3, "curious": 0.6},
        "content": content,
        "facts": [{"claim": "自動要約", "confidence": 0.8, "source": "memory"}],
    }
    return {"ok": True, "draft": draft}


def _critic_mock(payload: Dict[str, Any]) -> Dict[str, Any]:
    draft = payload.get("draft") or {}
    rules = payload.get("rules") or {}
    context = payload.get("context") or {}
    scalars = context.get("scalars") or {}
    limits = payload.get("limits") or {}
    confidence = float(scalars.get("confidence", 1.0)) if scalars else 1.0

    # Start with simple dedup + trim per-line
    seen = set()
    edited_items: List[Dict[str, str]] = []
    for c in draft.get("content", []):
        typ = c.get("type", "say")
        text = (c.get("text") or "").strip()
        # trim overly long lines
        if len(text) > 40:
            text = text[:38].rstrip() + "…"
        if text in seen:
            continue
        seen.add(text)
        edited_items.append({"type": typ, "text": text})

    issues: List[Dict[str, str]] = []

    # Rule B: ensure a single question only
    # Mark questions as type 'question' or text ending with '？' or '?'
    q_indices = [i for i, it in enumerate(edited_items) if it.get("type") == "question" or (it.get("text", "").endswith("？") or it.get("text", "").endswith("?"))]
    if len(q_indices) > 1:
        # keep first, convert others to 'say'
        for idx in q_indices[1:]:
            edited_items[idx]["type"] = "say"
            issues.append({"severity": "fix", "tag": "multiple_questions", "note": "Removed extra question"})

    # Rule C: repetition suppression (first 3-6 chars)
    collapsed: List[Dict[str, str]] = []
    last_prefix = None
    for it in edited_items:
        text = it.get("text", "")
        prefix = text[:6]
        if last_prefix and prefix and prefix == last_prefix:
            # skip duplicate-style repeated line
            issues.append({"severity": "warn", "tag": "repeat", "note": f"Removed repeated prefix {prefix}"})
            continue
        collapsed.append(it)
        last_prefix = prefix
    edited_items = collapsed

    # Rule A: enforce max_total_chars
    max_chunks = limits.get("target_chunks", [1, 3])[1] if isinstance(limits.get("target_chunks"), (list, tuple)) else 3
    max_chars_per_chunk = limits.get("max_chars_per_chunk", 28)
    max_total_chars = max_chunks * max_chars_per_chunk

    total_chars = sum(len(it.get("text", "")) for it in edited_items)
    if total_chars > max_total_chars:
        # compress strategy: keep first few items, insert a short explanation 'つまり…', keep one question if exists
        new_items: List[Dict[str, str]] = []
        # find question if any
        q_item = None
        rest = []
        for it in edited_items:
            if (it.get("type") == "question") or it.get("text", "").endswith("？") or it.get("text", "").endswith("?"):
                if q_item is None:
                    q_item = it
                else:
                    # demote extra questions
                    it["type"] = "say"
                    rest.append(it)
            else:
                rest.append(it)
        # keep up to max_chunks -1 from rest, then add a 'つまり' line
        keep = max(0, max_chunks - 1)
        truncated = rest[:keep]
        # truncate each kept item to max_chars_per_chunk
        truncated_trunc = []
        for it in truncated:
            t = it.get("text", "")
            if len(t) > max_chars_per_chunk:
                t = t[:max_chars_per_chunk - 1].rstrip() + "…"
            truncated_trunc.append({"type": it.get("type"), "text": t})
        new_items.extend(truncated_trunc)
        # add compressed explanation
        new_items.append({"type": "say", "text": "つまり、要点だけ押さえればOK。"})
        if q_item:
            q_text = q_item.get("text", "")
            if len(q_text) > max_chars_per_chunk:
                # preserve question mark if present
                if q_text.endswith("？") or q_text.endswith("?"):
                    q_text = q_text[: max_chars_per_chunk - 2].rstrip() + "？"
                else:
                    q_text = q_text[: max_chars_per_chunk - 1].rstrip() + "…"
            new_items.append({"type": q_item.get("type"), "text": q_text, "_was_question": True})
        edited_items = new_items
        issues.append({"severity": "fix", "tag": "too_long", "note": "Compressed content to fit limits"})

    # Rule D: low confidence => ensure one disclaimer
    has_disc = any(it.get("type") == "disclaimer" for it in edited_items)
    if rules.get("must_include_disclaimer_if_low_conf") and confidence < 0.55 and not has_disc:
        edited_items.append({"type": "disclaimer", "text": "情報に自信がありません。"})
        issues.append({"severity": "fix", "tag": "added_disclaimer", "note": "Added disclaimer for low confidence"})

    # Rule E: neuro tempo injections (best-effort; limit +2 chunks)
    injections = 0
    glitch = float(scalars.get("glitch", 0.0)) if scalars else 0.0
    social_pressure = float(scalars.get("social_pressure", 0.0)) if scalars else 0.0
    if glitch > 0.6 and injections < 2:
        # insert self_correct near the front
        edited_items.insert(0, {"type": "self_correct", "text": "…あ、違うかも。"})
        injections += 1
        issues.append({"severity": "warn", "tag": "injected_self_correct", "note": "Inserted self-correction for high glitch"})
    if social_pressure > 0.75 and injections < 2:
        edited_items.insert(1, {"type": "aside", "text": "うん。"})
        injections += 1
        issues.append({"severity": "warn", "tag": "injected_aizuchi", "note": "Inserted aizuchi for social pressure"})

    # Final safety truncation: if still over max_total_chars, evenly truncate items
    max_chunks = limits.get("target_chunks", [1, 3])[1] if isinstance(limits.get("target_chunks"), (list, tuple)) else 3
    max_chars_per_chunk = limits.get("max_chars_per_chunk", 28)
    max_total_chars = max_chunks * max_chars_per_chunk
    total_chars = sum(len(it.get("text", "")) for it in edited_items)
    if total_chars > max_total_chars:
        n = max(1, len(edited_items))
        per = max(8, max_total_chars // n)
        for it in edited_items:
            t = it.get("text", "")
            if len(t) > per:
                # preserve question mark for originally-question items
                if it.get("_was_question"):
                    it["text"] = t[: per - 2].rstrip() + "？"
                    it.pop("_was_question", None)
                else:
                    it["text"] = t[: per - 1].rstrip() + "…"
        issues.append({"severity": "fix", "tag": "final_truncate", "note": "Evenly truncated items to meet total chars"})

    edited = {
        "intent": draft.get("intent"),
        "key_points": draft.get("key_points"),
        "tone": draft.get("tone"),
        "content": edited_items,
        "facts": draft.get("facts", []),
    }
    return {"ok": True, "edited": edited, "issues": issues}


def _finalizer_mock(payload: Dict[str, Any]) -> Dict[str, Any]:
    # This mock is a thin passthrough; actual finalization is done in FinalizerAgent using speech_brain
    edited = payload.get("edited") or {}
    # return edited to indicate success; finalizer agent will call speech_brain.make_speech_plan
    return {"ok": True, "edited": edited}
