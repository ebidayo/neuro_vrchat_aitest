"""Time-related utilities for greet type decision.
"""
from __future__ import annotations

from datetime import datetime


def decide_greet_type(hour: int) -> str:
    """Return greet type based on hour (local hour 0-23).

    - 05-10: morning
    - 11-17: day
    - 18-04: night
    """
    h = int(hour) % 24
    if 5 <= h <= 10:
        return "morning"
    if 11 <= h <= 17:
        return "day"
    return "night"


def decide_greet_type_from_dt(dt: datetime) -> str:
    return decide_greet_type(dt.hour)
