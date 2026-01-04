from neuro_vrchat_ai import main


def test_demo_smoke_agents_enabled():
    out = main.run_demo_smoke(agents_enabled=True, steps=6, seed=123)
    assert out["ok"] is True
    assert out["plans"] >= 2
    assert "SEARCH" in out["states"]


def test_demo_smoke_agents_enabled_via_config_dict():
    cfg = {"agents": {"enabled": True}}
    enabled = main.resolve_agents_enabled_from_config(cfg)
    out = main.run_demo_smoke(agents_enabled=enabled, steps=6, seed=123)
    assert out["ok"] is True
    assert out["plans"] >= 2
    assert "SEARCH" in out["states"]


def test_demo_smoke_emits_idle_presence_chunk():
    out = main.run_demo_smoke(agents_enabled=False, steps=6, seed=123, force_idle_presence=True)
    assert out["ok"] is True
    assert out.get("idle_presence_emits", 0) >= 1
    assert "IDLE" in (out.get("emitted_states") or [])
