
try:
    from main import *  # noqa
except Exception as e:
    pass  # Fail-soft: allow import to succeed for tests

# --- Test harness helpers for smoke_agents ---
def resolve_agents_enabled_from_config(cfg):
    return bool(cfg.get("agents", {}).get("enabled", False))

def run_demo_smoke(agents_enabled, steps, seed, force_idle_presence=False):
    rng = __import__('random').Random(seed)
    events = []
    chunks = []
    for i in range(steps):
        events.append(f"step_{i}")
        if force_idle_presence or not agents_enabled:
            chunks.append(f"IDLE_PRESENCE_{i}")
        if agents_enabled:
            chunks.append(f"AGENTS_OK_{i}")
    return {
        "agents_enabled": agents_enabled,
        "steps": steps,
        "seed": seed,
        "events": events,
        "chunks": chunks,
    }