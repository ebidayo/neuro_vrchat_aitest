from core.speech_brain import build_search_intro_plan, build_search_result_plan

EPS = 1e-6


def _check_plan_ranges(plan):
    sp = plan.get("speech_plan") or []
    for c in sp:
        osc = c.get("osc")
        if isinstance(osc, dict):
            a = osc.get("N_Arousal")
            l = osc.get("N_Look")
            if a is not None:
                assert -EPS <= a <= 1.0 + EPS
            if l is not None:
                assert -EPS <= l <= 1.0 + EPS


def test_search_intro_and_result_osc_ranges():
    intro = build_search_intro_plan(glitch=0.2, curiosity=0.3, confidence=0.8, seed=42)
    _check_plan_ranges(intro)

    res = {"ok": True, "items": [{"title": "A"}, {"title": "B"}, {"title": "C"}], "query": "q", "confidence": 0.7}
    result_plan = build_search_result_plan(res, seed=42)
    _check_plan_ranges(result_plan)
