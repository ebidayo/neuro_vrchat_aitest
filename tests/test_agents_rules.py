import pytest
from core.agents.mock_llm import call_llm


def make_long_draft():
    # create a draft with repeated lines and multiple questions to trigger critic rules
    content = [
        {"type": "say", "text": "要点Aについて詳しく説明します。長いテキストが続きます。"},
        {"type": "say", "text": "要点Aについて詳しく説明します。長いテキストが続きます。"},
        {"type": "say", "text": "要点Bはこうです。"},
        {"type": "say", "text": "つまり、追加の説明をします。"},
        {"type": "say", "text": "最後に確認ですか？"},
        {"type": "say", "text": "他にも確認しますか？"},
    ]
    return {"intent": "answer", "content": content, "key_points": ["A","B","C"]}


def test_critic_compresses_and_limits_questions_and_adds_disclaimer():
    draft = make_long_draft()
    payload = {
        "role": "critic",
        "state": "TALK",
        "user_text": "長い内容",
        "draft": draft,
        "context": {"scalars": {"confidence": 0.3, "glitch": 0.7, "social_pressure": 0.8}},
        "rules": {"must_include_disclaimer_if_low_conf": True, "no_long_monologue": True, "neuro_style": True},
        "limits": {"target_chunks": [1, 2], "max_chars_per_chunk": 20},
    }

    res = call_llm(payload)
    assert res.get("ok") is True
    edited = res.get("edited")

    # total chars should not exceed max_total_chars (2 * 20 = 40)
    total_chars = sum(len(it.get("text","")) for it in edited.get("content", []))
    assert total_chars <= 40 + 5

    # only one question should remain
    q_count = sum(1 for it in edited.get("content", []) if it.get("type") == "question" or it.get("text"," ").endswith("？") or it.get("text"," ").endswith("?"))
    assert q_count == 1

    # disclaimer present exactly once (since low confidence)
    disc_count = sum(1 for it in edited.get("content", []) if it.get("type") == "disclaimer")
    assert disc_count == 1

    # repetition suppressed (no exact duplicate lines)
    texts = [it.get("text") for it in edited.get("content", [])]
    assert len(texts) == len(set(texts))


def test_pipeline_smoke_with_agents_enabled_returns_speech_plan():
    from core.agents import AgentPipeline
    pipeline = AgentPipeline.with_mock()
    res = pipeline.generate(state="TALK", user_text="スモークテストのための短文です。", context={}, limits={"target_chunks": [1, 3]}, scalars={"confidence": 0.8, "glitch": 0.0})
    assert res.get("ok") is True
    sp = res.get("speech_plan")
    assert isinstance(sp, list)
    assert len(sp) > 0
