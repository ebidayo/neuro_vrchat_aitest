"""Alert-specific speech plan generator for v1.2.

Produces concise, emergency-style speech plans with OSC N_* fields
and minimal 'chunks' legacy output for compatibility.
"""
from datetime import datetime
from typing import Dict, Any, List

MIN_PAUSE = 120


def _mk_chunk(cid: int, ctype: str, text: str, pause_ms: int, osc: Dict[str, Any], confidence_tag: str = "med") -> Dict[str, Any]:
    return {
        "id": f"a{cid}",
        "type": ctype,
        "text": text,
        "pause_ms": int(pause_ms),
        "osc": osc or {},
        "confidence_tag": confidence_tag,
    }


def build_alert_speech_plan(ev: Dict[str, Any], scalars: Dict[str, float], *, user_loc: Dict[str, Any] | None = None, is_update: bool = False, is_clear: bool = False) -> Dict[str, Any]:
    """Build a short alert speech plan for event `ev`.

    ev: {type,severity,event_time,source,region_code,message,alert_event_id,update_seq}
    scalars: contains current arousal/valence/confidence etc.
    """
    typ = (ev or {}).get("type", "unknown")
    severity = int((ev or {}).get("severity", 0))
    region = (ev or {}).get("region_code", "unknown")
    message = (ev or {}).get("message", "")
    is_dummy = (ev or {}).get("source", "DUMMY") == "DUMMY"

    # Base OSC targets for ALERT
    cur_arousal = float(scalars.get("arousal", 0.1))
    cur_valence = float(scalars.get("valence", 0.0))

    n_state = int(5)  # State.ALERT value per State enum
    n_arousal = max(cur_arousal, 0.85)
    n_valence = min(cur_valence, -0.35)
    n_look = 0.95

    # gesture heuristic
    if typ == "tsunami" or severity >= 9:
        n_gesture = 0.75
    elif typ == "earthquake":
        n_gesture = 0.55
    else:
        n_gesture = 0.45

    chunks: List[Dict[str, Any]] = []

    cid = 1

    if is_clear:
        # peaceful clear message
        chunks.append(_mk_chunk(cid, "say", "ひとまず落ち着いたみたい。", 160, {"N_State": n_state, "N_Arousal": 0.35, "N_Valence": 0.0, "N_Gesture": 0.2, "N_Look": n_look}, confidence_tag="med"))
        cid += 1
        chunks.append(_mk_chunk(cid, "disclaimer", "でも油断せず、公式の最終報も確認してね。", 180, {"N_State": n_state, "N_Arousal": 0.25, "N_Valence": 0.0, "N_Gesture": 0.15, "N_Look": n_look}, confidence_tag="med"))
        cid += 1
        return {"speech_plan": chunks, "chunks": _to_legacy(chunks)}

    if is_update:
        # short lead-in then compressed details
        chunks.append(_mk_chunk(cid, "alert", "続報。", 140, {"N_State": n_state, "N_Arousal": n_arousal, "N_Valence": n_valence, "N_Gesture": n_gesture, "N_Look": n_look}, confidence_tag=("low" if is_dummy else "med")))
        cid += 1
        # follow with compressed summary depending on type
        if typ == "tsunami" or severity >= 9:
            chunks.append(_mk_chunk(cid, "say", f"{region} の沿岸域は高い危険度です。", 160, {"N_State": n_state, "N_Arousal": n_arousal, "N_Valence": n_valence, "N_Gesture": n_gesture, "N_Look": n_look}, confidence_tag=("low" if is_dummy else "med")))
            cid += 1
        else:
            chunks.append(_mk_chunk(cid, "say", f"{region} 付近で揺れが続いています。注意してください。", 160, {"N_State": n_state, "N_Arousal": n_arousal, "N_Valence": n_valence, "N_Gesture": n_gesture, "N_Look": n_look}, confidence_tag=("low" if is_dummy else "med")))
            cid += 1
        chunks.append(_mk_chunk(cid, "disclaimer", "続報で変わるかも。公式の更新も見てね。", 180, {"N_State": n_state, "N_Arousal": 0.4, "N_Valence": n_valence, "N_Gesture": 0.2, "N_Look": n_look}, confidence_tag=("low" if is_dummy else "med")))
        cid += 1
        return {"speech_plan": chunks, "chunks": _to_legacy(chunks)}

    # New alert
    if typ == "tsunami" or severity >= 9:
        # example tsunami template
        chunks.append(_mk_chunk(cid, "alert", "津波警報。海から離れて、高いところへ。", 180, {"N_State": n_state, "N_Arousal": n_arousal, "N_Valence": n_valence, "N_Gesture": 0.8, "N_Look": n_look}, confidence_tag=("low" if is_dummy else "med")))
        cid += 1
        chunks.append(_mk_chunk(cid, "say", f"対象: {region}。", 140, {"N_State": n_state, "N_Arousal": n_arousal, "N_Valence": n_valence, "N_Gesture": 0.6, "N_Look": n_look}, confidence_tag=("low" if is_dummy else "med")))
        cid += 1
        # Insert geo-based explanation if available
        try:
            from core.geo_explain import build_geo_chunks_for_alert
            geo = build_geo_chunks_for_alert(ev, user_loc or {}, scalars.get("confidence", 0.5), scalars.get("arousal", 0.1))
            for g in geo:
                # convert g into speech_plan chunk using _mk_chunk structure
                chunks.append(_mk_chunk(cid, g.get("type", "say"), g.get("text", ""), int(g.get("pause_ms", 160)), g.get("osc", {}), confidence_tag=g.get("confidence_tag", "low")))
                cid += 1
        except Exception:
            # failing geo explain should not break alert creation
            pass

        chunks.append(_mk_chunk(cid, "disclaimer", "続報で変わるかも。公式の更新も見てね。", 180, {"N_State": n_state, "N_Arousal": 0.4, "N_Valence": n_valence, "N_Gesture": 0.3, "N_Look": n_look}, confidence_tag=("low" if is_dummy else "med")))
        cid += 1
    elif typ == "earthquake":
        chunks.append(_mk_chunk(cid, "alert", "地震。揺れたね。", 140, {"N_State": n_state, "N_Arousal": n_arousal, "N_Valence": n_valence, "N_Gesture": n_gesture, "N_Look": n_look}, confidence_tag=("low" if is_dummy else "med")))
        cid += 1
        chunks.append(_mk_chunk(cid, "say", f"震度{severity}くらい。", 160, {"N_State": n_state, "N_Arousal": n_arousal, "N_Valence": n_valence, "N_Gesture": n_gesture, "N_Look": n_look}, confidence_tag=("low" if is_dummy else "med")))
        cid += 1
        chunks.append(_mk_chunk(cid, "say", "落下物/余震に注意。", 160, {"N_State": n_state, "N_Arousal": n_arousal, "N_Valence": n_valence, "N_Gesture": n_gesture, "N_Look": n_look}, confidence_tag=("low" if is_dummy else "med")))
        cid += 1
        chunks.append(_mk_chunk(cid, "disclaimer", "情報は更新される。無理せず安全第一。", 180, {"N_State": n_state, "N_Arousal": 0.4, "N_Valence": n_valence, "N_Gesture": 0.2, "N_Look": n_look}, confidence_tag=("low" if is_dummy else "med")))
        cid += 1
    else:
        # generic alert fallback
        chunks.append(_mk_chunk(cid, "alert", "緊急情報が入りました。詳細を確認してください。", 180, {"N_State": n_state, "N_Arousal": n_arousal, "N_Valence": n_valence, "N_Gesture": n_gesture, "N_Look": n_look}, confidence_tag=("low" if is_dummy else "med")))
        cid += 1
        chunks.append(_mk_chunk(cid, "disclaimer", "続報で変わるかも。公式の更新も見てね。", 180, {"N_State": n_state, "N_Arousal": 0.4, "N_Valence": n_valence, "N_Gesture": 0.3, "N_Look": n_look}, confidence_tag=("low" if is_dummy else "med")))
        cid += 1

    return {"speech_plan": chunks, "chunks": _to_legacy(chunks)}


def _to_legacy(speech_plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Convert speech_plan entries to legacy chunk dicts with key expressive fields
    legacy = []
    for sp in speech_plan:
        osc = sp.get("osc", {})
        legacy.append({
            "text": sp.get("text", ""),
            "pause_ms": sp.get("pause_ms", MIN_PAUSE),
            "gesture": float(osc.get("N_Gesture", 0.0)),
            "look_x": float((osc.get("N_Look", 0.5) * 2.0) - 1.0),
            "arousal": float(osc.get("N_Arousal", 0.0)),
            "valence": float(osc.get("N_Valence", 0.0)),
            "glitch": 0.0,
        })
    return legacy
