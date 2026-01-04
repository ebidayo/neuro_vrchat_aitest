from typing import Any, Dict
from .types import PlannerInput, PlannerOutput
from .mock_llm import call_llm

class PlannerAgent:
    def __init__(self, llm_call=call_llm):
        self.call_llm = llm_call

    def plan(self, inp: PlannerInput) -> PlannerOutput:
        # enforce planner-output shape: key_points <=3, content 2..5, single follow-up question
        payload = dict(inp)
        payload["role"] = "planner"
        res = self.call_llm(payload)
        if not res.get("ok"):
            return res
        draft = res.get("draft") or {}
        # normalize key_points
        kps = (draft.get("key_points") or [])[:3]
        # ensure content length 2..5
        content = draft.get("content") or []
        if len(content) < 2:
            # pad with a simple rephrase and a question
            content = content + [{"type":"say","text":"要点をまとめます。"}]
        content = content[:5]
        # ensure final follow-up question present
        if not any((c.get("type") == "question") or (c.get("text"," ").endswith("？") or c.get("text"," ").endswith("?")) for c in content):
            # ensure last element is a question
            if content:
                content[-1] = {"type":"say","text":"ざっくりでいいですか？"}
            else:
                content = [{"type":"say","text":"ざっくりでいいですか？"}]

        draft["key_points"] = kps
        draft["content"] = content
        res["draft"] = draft
        return res
