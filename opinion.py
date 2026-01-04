from dataclasses import dataclass
import math

@dataclass
class OpinionState:
    concise_vs_detailed: float = 0.0
    playful_vs_serious: float = 0.0
    risk_averse_vs_bold: float = 0.0
    updated_ts: float = 0.0

def update_opinion(state, signals, now_ts, alpha=0.01):
    # signals: dict with optional keys matching OpinionState fields
    new = OpinionState(
        concise_vs_detailed=state.concise_vs_detailed,
        playful_vs_serious=state.playful_vs_serious,
        risk_averse_vs_bold=state.risk_averse_vs_bold,
        updated_ts=now_ts,
    )
    for k in ["concise_vs_detailed", "playful_vs_serious", "risk_averse_vs_bold"]:
        if k in signals:
            v = float(signals[k])
            old = getattr(new, k)
            ewma = (1 - alpha) * old + alpha * v
            ewma = max(-1.0, min(1.0, ewma))
            ewma = float(f"{ewma:.4f}")
            setattr(new, k, ewma)
    return new
