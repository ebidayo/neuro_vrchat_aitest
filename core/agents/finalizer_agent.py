from typing import Any, Dict, List
from .types import FinalizerInput, FinalizerOutput
from core.speech_brain import make_speech_plan, MAX_CHUNKS

class FinalizerAgent:
    def __init__(self):
        pass

    def finalize(self, inp: FinalizerInput) -> FinalizerOutput:
        edited = inp.get("edited") or {}
        scalars = inp.get("scalars") or {}
        limits = inp.get("limits") or {}

        # Respect edited.content elements individually and convert to speech chunks
        try:
            speech_plan_accum: List[Dict] = []
            target = limits.get("target_chunks") or [1, MAX_CHUNKS]
            try:
                max_says = int(target[1])
            except Exception:
                max_says = MAX_CHUNKS
            say_count = 0

            for idx, it in enumerate(edited.get("content", [])):
                typ = it.get("type", "say")
                txt = (it.get("text") or "").strip()
                if not txt:
                    continue

                if typ == "disclaimer":
                    disc_chunk = {"id": f"disc{idx}", "type": "disclaimer", "text": txt, "pause_ms": 160, "osc": {"N_State": "TALK", "N_Arousal": 0.28, "N_Valence": -0.05, "N_Gesture": 0.15, "N_Look": 0.9}}
                    speech_plan_accum.append(disc_chunk)
                    continue

                if typ == "question" or txt.endswith("？") or txt.endswith("?"):
                    q_chunk = {"id": f"q{idx}", "type": "question", "text": txt, "pause_ms": 160, "osc": {"N_State": "TALK", "N_Arousal": 0.45, "N_Valence": 0.0, "N_Gesture": 0.2, "N_Look": 0.9}}
                    speech_plan_accum.append(q_chunk)
                    continue

                # For other types, use make_speech_plan to split and apply light injections
                sub_plan = make_speech_plan(txt, confidence=float(scalars.get("confidence", 0.8)), curiosity=float(scalars.get("curiosity", 0.0)), seed=limits.get("seed"), use_agents=False)
                sp = sub_plan.get("speech_plan", [])
                for c in sp:
                    if c.get("type") == "say":
                        if say_count < max_says:
                            speech_plan_accum.append(c)
                            say_count += 1
                        else:
                            # skip extra say chunks
                            continue
                    else:
                        speech_plan_accum.append(c)

            # ensure disclaimer if low confidence and not present
            conf = float(scalars.get("confidence", 0.8))
            if conf < 0.55 and not any(c.get("type") == "disclaimer" for c in speech_plan_accum):
                disc_chunk = {"id": "disc_final", "type": "disclaimer", "text": "情報に自信がありません。", "pause_ms": 160, "osc": {"N_State": "TALK", "N_Arousal": 0.28, "N_Valence": -0.05, "N_Gesture": 0.15, "N_Look": 0.9}}
                speech_plan_accum.append(disc_chunk)

            return {"ok": True, "speech_plan": speech_plan_accum}
        except Exception as e:
            return {"ok": False, "error": str(e)}
