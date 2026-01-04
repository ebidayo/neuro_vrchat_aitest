from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TypedDict

class PlannerInput(TypedDict, total=False):
    role: str
    state: str
    user_text: str
    context: Dict[str, Any]
    limits: Dict[str, Any]

class PlannerDraft(TypedDict, total=False):
    intent: str
    key_points: List[str]
    tone: Dict[str, float]
    content: List[Dict[str, str]]
    facts: List[Dict[str, Any]]

class PlannerOutput(TypedDict, total=False):
    ok: bool
    draft: PlannerDraft
    error: Optional[str]

class CriticInput(TypedDict, total=False):
    role: str
    state: str
    user_text: str
    draft: PlannerDraft
    context: Dict[str, Any]
    rules: Dict[str, bool]

class CriticOutput(TypedDict, total=False):
    ok: bool
    edited: PlannerDraft
    issues: List[Dict[str, str]]
    error: Optional[str]

class FinalizerInput(TypedDict, total=False):
    role: str
    state: str
    edited: PlannerDraft
    scalars: Dict[str, Any]
    limits: Dict[str, Any]

class FinalizerOutput(TypedDict, total=False):
    ok: bool
    speech_plan: List[Dict[str, Any]]
    error: Optional[str]
