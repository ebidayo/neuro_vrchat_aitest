import pytest
from core.agents import AgentPipeline


def test_pipeline_generates_speech_plan():
    pipeline = AgentPipeline.with_mock()
    res = pipeline.generate(state="TALK", user_text="テスト情報を確認して", context={}, limits={"target_chunks": [1, 4]}, scalars={"confidence": 0.8})
    assert res.get("ok") is True
    sp = res.get("speech_plan")
    assert isinstance(sp, list)
    # must have at least one chunk with id/type/text/pause_ms
    assert any(isinstance(c.get("id"), str) for c in sp)
    assert any(isinstance(c.get("text"), str) for c in sp)
    assert any(isinstance(c.get("pause_ms"), int) for c in sp)


def test_low_confidence_includes_disclaimer():
    pipeline = AgentPipeline.with_mock()
    res = pipeline.generate(state="TALK", user_text="不確かな情報", context={}, limits={}, scalars={"confidence": 0.3})
    assert res.get("ok") is True
    sp = res.get("speech_plan")
    assert any(c.get("type") == "disclaimer" for c in sp), "Expected a disclaimer chunk when confidence is low"


def test_respects_target_chunks_upper_bound():
    pipeline = AgentPipeline.with_mock()
    res = pipeline.generate(state="TALK", user_text="多めのポイントを含むテキストです。長めの文章を入れても、最終的なチャンク数は制限されるはずです。", context={}, limits={"target_chunks": [1, 2]}, scalars={"confidence": 0.8})
    assert res.get("ok") is True
    sp = res.get("speech_plan")
    # count 'say' chunks and ensure <= 2
    say_count = sum(1 for c in sp if c.get("type") == "say")
    assert say_count <= 2


def test_pipeline_failure_falls_back_to_legacy_make_speech_plan():
    from core import speech_brain

    class BadPipeline:
        def generate(self, **kwargs):
            raise RuntimeError("boom")

    # ensure we get a plan and not an exception
    plan = speech_brain.make_speech_plan("テストのフォールバック", use_agents=True, agent_pipeline=BadPipeline())
    assert isinstance(plan, dict)
    assert "speech_plan" in plan and isinstance(plan["speech_plan"], list)
