import math
from learned_alias_store import AliasEntry

def decay_weight(weight: float, dt: float, tau: float) -> float:
    if tau <= 0 or dt <= 0:
        return weight
    return float(f"{weight * math.exp(-dt / tau):.4f}")

def update_alias(store, alias: str, now_ts: float, cfg) -> AliasEntry:
    tau = float(cfg.get("decay_tau_sec", 604800))
    init_weight = float(cfg.get("init_weight", 0.10))
    inc_weight = float(cfg.get("inc_weight", 0.10))
    promote_threshold = float(cfg.get("promote_threshold", 0.60))
    entry = store.get(alias)
    if entry:
        dt = max(0, now_ts - entry.last_seen_ts)
        decayed = decay_weight(entry.weight, dt, tau)
        new_weight = min(1.0, decayed + inc_weight)
        count = entry.count + 1
    else:
        new_weight = init_weight
        count = 1
    new_weight = float(f"{max(0.0, min(1.0, new_weight)):.4f}")
    entry = AliasEntry(alias=alias, weight=new_weight, last_seen_ts=now_ts, count=count, confirmed=new_weight >= promote_threshold)
    store.upsert(entry)
    return entry

def is_confirmed(entry, cfg) -> bool:
    promote_threshold = float(cfg.get("promote_threshold", 0.60))
    return entry.weight >= promote_threshold

def get_confirmed_aliases(store, cfg) -> list:
    promote_threshold = float(cfg.get("promote_threshold", 0.60))
    entries = store.get_all()
    return [e.alias for e in entries if e.weight >= promote_threshold]
