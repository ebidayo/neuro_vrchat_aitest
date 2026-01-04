from neuro_vrchat_ai.core.state_machine import StateMachine, State
from neuro_vrchat_ai.core.speech_brain import build_search_intro_plan, build_search_result_plan

# numerical epsilon for float-range tolerance
EPS = 1e-6


def test_net_query_interrupt_flow_talk_to_search_to_talk():
    sm = StateMachine()
    # start() is unnecessary
    sm.state = State.TALK

    query = "VRChatの最近の話題を教えて"
    payload = {"query": query, "sources": ["news", "vrchat"]}

    # 1) TALK中に net_query が来る
    sm.on_event("net_query", payload)

    # 2) 即時には SEARCH に入らない（チャンク境界待ち）
    assert sm.state == State.TALK

    # 3) チャンク境界で SEARCH に入る
    sm.mark_speech_done()
    assert sm.state == State.SEARCH

    # 4) SEARCH intro plan is producible
    intro = build_search_intro_plan(glitch=sm.glitch, curiosity=sm.curiosity, confidence=sm.confidence, seed=42)
    sp_intro = intro.get("speech_plan") or []
    assert len(sp_intro) >= 1
    assert any(c.get("type") in ("think", "say") for c in sp_intro)

    # Ensure at least one intro chunk has an OSC map and N_State == 'SEARCH'
    osc_intro = [c for c in sp_intro if isinstance(c.get("osc"), dict)]
    assert len(osc_intro) > 0
    search_chunks = [c for c in osc_intro if c.get("osc", {}).get("N_State") == "SEARCH"]
    assert len(search_chunks) > 0

    # Numeric sanity checks for SEARCH intro: require at least one SEARCH chunk with high look & elevated arousal
    assert any(
        ((c["osc"].get("N_Look") is None or c["osc"].get("N_Look") + EPS >= 0.95) and
         (c["osc"].get("N_Arousal") is None or c["osc"].get("N_Arousal") + EPS >= 0.65))
        for c in search_chunks
    )

    # 5) Inject search_result (Fake) and verify we return to TALK
    fake_result = {
        "ok": True,
        "query": query,
        "from_cache": False,
        "items": [
            {"title": "A", "summary": "要点その1。詳細は省略。", "url": "http://example.com/a", "source": "dummy"},
            {"title": "B", "summary": "要点その2。", "url": "http://example.com/b", "source": "dummy"},
            {"title": "C", "summary": "要点その3。", "url": "http://example.com/c", "source": "dummy"},
        ],
        "error": None,
        "ts": 1700000000.0,
    }
    sm.on_event("search_result", fake_result)
    assert sm.state == State.TALK

    # 6) TALK復帰後に result_plan を生成でき、構造が「要点3つ→つまり→質問」
    plan = build_search_result_plan(fake_result, seed=42)
    sp = plan.get("speech_plan") or []
    assert any("要点" in (c.get("text") or "") for c in sp)

    # numbered bullets 1) 2) 3)
    assert any((c.get("text") or "").startswith("1)") for c in sp)
    assert any((c.get("text") or "").startswith("2)") for c in sp)
    assert any((c.get("text") or "").startswith("3)") for c in sp)

    # explanation contains "つまり"
    assert any("つまり" in (c.get("text") or "") for c in sp)

    # Ensure the introductory '要点' chunk has an OSC map with N_State == 'TALK'
    intro_chunks = [c for c in sp if "要点" in (c.get("text") or "")]
    assert len(intro_chunks) > 0
    first = intro_chunks[0]
    osc = first.get("osc") if isinstance(first.get("osc"), dict) else {}
    assert osc.get("N_State") == "TALK"

    # Numeric sanity checks for TALK intro: look in 0.80..0.95 and arousal in 0.45..0.65 if present
    look = osc.get("N_Look")
    arousal = osc.get("N_Arousal")
    if look is not None:
        assert 0.80 - EPS <= look <= 0.95 + EPS
    if arousal is not None:
        assert 0.45 - EPS <= arousal <= 0.65 + EPS

    # follow-up question is exactly one (ends with ?/？ or type==question)
    q_chunks = [c for c in sp if (c.get("type") == "question") or ((c.get("text") or "").strip().endswith("？")) or ((c.get("text") or "").strip().endswith("?"))]
    assert len(q_chunks) == 1
