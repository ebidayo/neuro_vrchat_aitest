import pytest
import random
from debate import can_debate
from debate_structure import build_debate_response
from opinion import OpinionState, update_opinion

# Minimal planner/finalizer harness
class DummyEmergency:
    def __init__(self, active=False):
        self._active = active
    def is_active(self):
        return self._active

def planner(context, cfg, opinion_state):
    # Simulate planner output JSON
    out = {
        "response_mode": "normal",
        "response_strength": context.get("response_strength", "low"),
        "opinion_bias": {
            "concise_vs_detailed": opinion_state.concise_vs_detailed,
            "playful_vs_serious": opinion_state.playful_vs_serious,
            "risk_averse_vs_bold": opinion_state.risk_averse_vs_bold,
        },
    }
    if cfg.get("personality", {}).get("debate", {}).get("enabled", False):
        if can_debate(context):
            out["response_mode"] = "debate"
            out["debate"] = {
                "claim_summary": "寿司は最高",
                "counter_point": "健康面"
            }
    return out

def finalizer(planner_json, cfg, context):
    # Emergency suppression
    if context.get("emergency_active"):
        return ["EMERGENCY"]
    if planner_json.get("response_mode") == "debate" and planner_json.get("debate"):
        claim = planner_json["debate"].get("claim_summary", "")
        counter = planner_json["debate"].get("counter_point", "")
        chunks = build_debate_response(claim, counter)
        # Hesitation (deterministic)
        hes_cfg = cfg.get("personality", {}).get("debate", {}).get("hesitation", {})
        if hes_cfg.get("enabled", True):
            # Use session_id+turn_index for deterministic seed
            session_id = context.get("session_id", "A")
            turn_index = context.get("turn_index", 0)
            seed = hash((session_id, turn_index))
            rng = random.Random(seed)
            if rng.random() < hes_cfg.get("prob", 0.20):
                prefix = "えっと、" if (seed % 2 == 0) else "うーん、"
                chunks[0] = prefix + chunks[0]
        return chunks
    # Normal: apply opinion_bias as style (simulate)
    bias = planner_json.get("opinion_bias", {})
    base = "私はそう思います。"
    if bias.get("concise_vs_detailed", 0.0) > 0.5:
        return [base, "理由はたくさんありますが、ここでは省略します。"]
    elif bias.get("playful_vs_serious", 0.0) < -0.5:
        return [base + "（冗談です）"]
    else:
        return [base]

def make_cfg(debate_enabled=True):
    return {
        "personality": {
            "opinion": {"enabled": True, "alpha": 0.01},
            "debate": {"enabled": debate_enabled, "hesitation": {"enabled": True, "prob": 0.20}},
        }
    }

def test_debate_allowed_path():
    context = {
        "behavior_mode": "TALK_PRIMARY",
        "addressed": True,
        "response_strength": "high",
        "text": "寿司は最高だ",
        "emergency": DummyEmergency(False),
        "emergency_active": False,
        "topic": "食べ物",
        "session_id": "A",
        "turn_index": 1
    }
    op = OpinionState()
    cfg = make_cfg(True)
    planner_json = planner(context, cfg, op)
    chunks = finalizer(planner_json, cfg, context)
    assert len(chunks) == 3
    assert "前提" in chunks[0]
    assert "説明" in chunks[1]
    assert "成り立たない" in chunks[2]

def test_debate_denied_by_denylist():
    context = {
        "behavior_mode": "TALK_PRIMARY",
        "addressed": True,
        "response_strength": "high",
        "text": "政治は大事だ",
        "emergency": DummyEmergency(False),
        "emergency_active": False,
        "topic": "政治",
        "session_id": "A",
        "turn_index": 2
    }
    op = OpinionState()
    cfg = make_cfg(True)
    planner_json = planner(context, cfg, op)
    chunks = finalizer(planner_json, cfg, context)
    # Should not be debate
    assert not (len(chunks) == 3 and "前提" in chunks[0])

def test_no_debate_when_not_addressed():
    context = {
        "behavior_mode": "TALK_PRIMARY",
        "addressed": False,
        "response_strength": "low",
        "text": "寿司は最高だ",
        "emergency": DummyEmergency(False),
        "emergency_active": False,
        "topic": "食べ物",
        "session_id": "A",
        "turn_index": 3
    }
    op = OpinionState()
    cfg = make_cfg(True)
    planner_json = planner(context, cfg, op)
    chunks = finalizer(planner_json, cfg, context)
    # Should not be debate
    assert not (len(chunks) == 3 and "前提" in chunks[0])

def test_emergency_active_suppresses():
    context = {
        "behavior_mode": "TALK_PRIMARY",
        "addressed": True,
        "response_strength": "high",
        "text": "寿司は最高だ",
        "emergency": DummyEmergency(True),
        "emergency_active": True,
        "topic": "食べ物",
        "session_id": "A",
        "turn_index": 4
    }
    op = OpinionState()
    cfg = make_cfg(True)
    planner_json = planner(context, cfg, op)
    chunks = finalizer(planner_json, cfg, context)
    assert chunks == ["EMERGENCY"]

def test_determinism():
    context = {
        "behavior_mode": "TALK_PRIMARY",
        "addressed": True,
        "response_strength": "high",
        "text": "寿司は最高だ",
        "emergency": DummyEmergency(False),
        "emergency_active": False,
        "topic": "食べ物",
        "session_id": "A",
        "turn_index": 5
    }
    op = OpinionState()
    cfg = make_cfg(True)
    planner_json = planner(context, cfg, op)
    chunks1 = finalizer(planner_json, cfg, context)
    chunks2 = finalizer(planner_json, cfg, context)
    assert chunks1 == chunks2
