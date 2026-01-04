import math
from typing import List, Tuple

def decay_factor(dt_sec: float, half_life_sec: float, floor_weight: float) -> float:
    """
    Returns decay factor in [floor_weight, 1.0].
    If half_life_sec <= 0, returns 1.0 (no decay).
    """
    if half_life_sec <= 0:
        return 1.0
    raw = 0.5 ** (dt_sec / half_life_sec)
    return max(raw, floor_weight)

def apply_decay_to_counts(
    items: List[Tuple[str, int, int]],
    now_ts: int,
    half_life_sec: float,
    floor_weight: float
) -> List[Tuple[str, float]]:
    """
    items: (token/hash, count, last_seen_ts)
    Returns: (token/hash, decayed_score), sorted by -score, token asc
    """
    scored = []
    for token, count, last_seen_ts in items:
        dt = now_ts - last_seen_ts
        f = decay_factor(dt, half_life_sec, floor_weight)
        score = count * f
        scored.append((token, score))
    # 決定的: -score, token asc
    scored.sort(key=lambda x: (-x[1], x[0]))
    return scored

def ewma_update(prev: float, x: float, alpha: float) -> float:
    """
    Exponential Weighted Moving Average update.
    """
    return alpha * x + (1 - alpha) * prev
