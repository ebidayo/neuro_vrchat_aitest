from typing import Any, Dict
from .types import CriticInput, CriticOutput
from .mock_llm import call_llm

class CriticAgent:
    def __init__(self, llm_call=call_llm):
        self.call_llm = llm_call

    def critique(self, inp: CriticInput) -> CriticOutput:
        payload = dict(inp)
        payload["role"] = "critic"
        return self.call_llm(payload)
