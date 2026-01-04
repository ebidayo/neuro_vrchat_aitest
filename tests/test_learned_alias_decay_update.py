import pytest
import time
from learned_alias_store import InMemoryLearnedAliasStore
from learned_alias_manager import update_alias, decay_weight, is_confirmed

def make_cfg(**kw):
    cfg = {
        "init_weight": 0.10,
        "inc_weight": 0.10,
        "promote_threshold": 0.60,
        "decay_tau_sec": 100.0,
    }
    cfg.update(kw)
    return cfg

def test_update_and_decay():
    store = InMemoryLearnedAliasStore()
    cfg = make_cfg()
    now = 1000.0
    # First insert
    entry1 = update_alias(store, "miso", now, cfg)
    assert abs(entry1.weight - 0.10) < 1e-4
    # Wait 50s, update again
    entry2 = update_alias(store, "miso", now+50, cfg)
    expected = decay_weight(0.10, 50, 100.0) + 0.10
    expected = float(f"{expected:.4f}")
    assert abs(entry2.weight - expected) < 1e-4
    # Promotion
    for i in range(10):
        entry2 = update_alias(store, "miso", now+100+i*10, cfg)
    assert is_confirmed(entry2, cfg)
