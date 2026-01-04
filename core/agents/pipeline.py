from typing import Any, Dict
from .planner_agent import PlannerAgent
from .critic_agent import CriticAgent
from .finalizer_agent import FinalizerAgent
from .mock_llm import call_llm

class AgentPipeline:
    def __init__(self, planner: PlannerAgent, critic: CriticAgent, finalizer: FinalizerAgent):
        self.planner = planner
        self.critic = critic
        self.finalizer = finalizer

    @classmethod
    def with_mock(cls):
        return cls(PlannerAgent(), CriticAgent(), FinalizerAgent())

    def generate(self, *, state: str, user_text: str, context: Dict[str, Any] = None, limits: Dict[str, Any] = None, scalars: Dict[str, Any] = None) -> Dict[str, Any]:
        # Run Planner -> Critic -> Finalizer, gracefully returning errors
        context = context or {}
        limits = limits or {}
        scalars = scalars or {}

        try:
            p_in = {"state": state, "user_text": user_text, "context": context, "limits": limits}
            p_out = self.planner.plan(p_in)
            if not p_out.get("ok"):
                return {"ok": False, "error": p_out.get("error")}

            draft = p_out.get("draft")
            c_in = {"state": state, "user_text": user_text, "draft": draft, "context": {"scalars": scalars}, "rules": {"must_include_disclaimer_if_low_conf": True, "no_long_monologue": True, "neuro_style": True}, "limits": limits}
            c_out = self.critic.critique(c_in)
            if not c_out.get("ok"):
                return {"ok": False, "error": c_out.get("error")}

            edited = c_out.get("edited")
            f_in = {"state": state, "edited": edited, "scalars": scalars, "limits": limits}
            f_out = self.finalizer.finalize(f_in)
            if not f_out.get("ok"):
                return {"ok": False, "error": f_out.get("error")}

            return {"ok": True, "speech_plan": f_out.get("speech_plan")}
        except Exception as e:
            return {"ok": False, "error": str(e)}
