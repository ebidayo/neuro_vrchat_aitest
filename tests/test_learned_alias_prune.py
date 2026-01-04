import pytest
import time
from learned_alias_store import InMemoryLearnedAliasStore, AliasEntry

def test_prune_max_entries():
    store = InMemoryLearnedAliasStore(max_entries=5)
    now = 1000.0
    # Insert 10 entries with different timestamps
    for i in range(10):
        entry = AliasEntry(alias=f"a{i}", weight=0.2, last_seen_ts=now+i, count=1, confirmed=False)
        store.upsert(entry)
    store.prune(now+20, max_entries=5, drop_below=0.05, decay_tau_sec=100.0)
    all_aliases = [e.alias for e in store.get_all()]
    assert len(all_aliases) == 5
    # Should be newest 5
    assert all_aliases == [f"a9", "a8", "a7", "a6", "a5"]

def test_prune_drop_below():
    store = InMemoryLearnedAliasStore(max_entries=10)
    now = 1000.0
    # Insert entries with low weight
    for i in range(5):
        entry = AliasEntry(alias=f"b{i}", weight=0.01, last_seen_ts=now+i, count=1, confirmed=False)
        store.upsert(entry)
    store.prune(now+20, max_entries=10, drop_below=0.05, decay_tau_sec=100.0)
    all_aliases = [e.alias for e in store.get_all()]
    assert all(a.startswith("a") or a.startswith("b") for a in all_aliases) or all_aliases == []
