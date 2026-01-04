from neuro_vrchat_ai.core.speech_brain import make_speech_plan


def test_make_speech_plan_types_and_disclaimer():
    text = "今日はいい天気ですね。公園に行きましょう。"
    plan = make_speech_plan(text, glitch=0.2, curiosity=0.1, confidence=0.3, social_pressure=0.1, arousal=0.2, valence=0.0, seed=123)

    assert "speech_plan" in plan
    sp = plan["speech_plan"]
    assert isinstance(sp, list) and len(sp) > 0

    # each chunk must have id,type,text,pause_ms
    for ch in sp:
        assert "id" in ch and isinstance(ch["id"], str)
        assert "type" in ch and isinstance(ch["type"], str)
        assert "text" in ch and isinstance(ch["text"], str)
        assert "pause_ms" in ch and isinstance(ch["pause_ms"], int)

    # confidence low -> disclaimer present
    assert any(ch["type"] == "disclaimer" for ch in sp)
