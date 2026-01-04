from core.speech_brain import build_search_intro_plan, build_search_result_plan, build_search_fail_plan


def test_search_intro_contains_think_and_aside():
    p = build_search_intro_plan(glitch=0.1, curiosity=0.2, confidence=0.8, seed=42)
    sp = p.get("speech_plan", [])
    types = [c.get("type") for c in sp]
    assert "think" in types and "aside" in types


def test_search_result_plan_has_points_and_disclaimer():
    # low confidence should force a disclaimer
    fake_res = {"ok": True, "items": [{"title": "A"}, {"title": "B"}, {"title": "C"}], "query": "q", "confidence": 0.4}
    p = build_search_result_plan(fake_res, seed=1)
    sp = p.get("speech_plan", [])
    say_count = sum(1 for c in sp if c.get("type") == "say")
    assert say_count >= 3
    assert any(c.get("type") == "disclaimer" for c in sp)


def test_search_fail_plan_has_disclaimer():
    p = build_search_fail_plan(error="timeout", seed=2)
    sp = p.get("speech_plan", [])
    assert any(c.get("type") == "disclaimer" for c in sp)


def test_search_result_plan_structure_and_followup():
    fake_res = {"ok": True, "items": [{"title": "First item title", "summary": "First summary."}, {"title": "Second item title", "summary": "Second summary."}, {"title": "Third item title", "summary": "Third summary."}], "query": "海 津波"}
    p = build_search_result_plan(fake_res, seed=5)
    sp = p.get("speech_plan", [])

    # intro must be present
    assert any((c.get("type") == "say" and "要点" in (c.get("text") or "")) for c in sp)

    # there must be three numbered bullets
    texts = [c.get("text", "") for c in sp if c.get("type") == "say"]
    assert any(t.startswith("1)") for t in texts)
    assert any(t.startswith("2)") for t in texts)
    assert any(t.startswith("3)") for t in texts)

    # explanation 'つまり' must appear in one chunk
    assert any((c.get("type") in ("say", "aside") and "つまり" in (c.get("text") or "")) for c in sp)

    # follow-up question must be present (ends with ? or starts with '確認。')
    assert any((c.get("type") == "say" and (c.get("text", "").strip().endswith("？") or c.get("text", "").startswith("確認"))) for c in sp)
