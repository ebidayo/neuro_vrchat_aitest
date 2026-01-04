import pytest
from core.memory.avatar_store import AvatarStore

@pytest.fixture
def store():
    return AvatarStore()

def test_record_avatar_seen_increments(store):
    k, aid = 'spk1', 'avatarA'
    store.record_avatar_seen(k, aid, 'Alice')
    store.record_avatar_seen(k, aid, 'Alice')
    stats = store.get_avatar_stats(k, aid)
    assert stats['seen_count'] == 2
    assert stats['avatar_name'] == 'Alice'

def test_upsert_and_distinct(store):
    k = 'spk2'
    aid1, aid2 = 'avatarA', 'avatarB'
    store.record_avatar_seen(k, aid1, 'Alpha')
    store.record_avatar_seen(k, aid2, 'Beta')
    stats1 = store.get_avatar_stats(k, aid1)
    stats2 = store.get_avatar_stats(k, aid2)
    assert stats1['avatar_name'] == 'Alpha'
    assert stats2['avatar_name'] == 'Beta'
    assert stats1['seen_count'] == 1
    assert stats2['seen_count'] == 1

def test_get_top_avatars(store):
    k = 'spk3'
    for i in range(5):
        store.record_avatar_seen(k, 'avatarA', 'A')
    for i in range(3):
        store.record_avatar_seen(k, 'avatarB', 'B')
    for i in range(2):
        store.record_avatar_seen(k, 'avatarC', 'C')
    tops = store.get_top_avatars(k, limit=2)
    assert len(tops) == 2
    assert tops[0]['avatar_id'] == 'avatarA'
    assert tops[1]['avatar_id'] == 'avatarB'
