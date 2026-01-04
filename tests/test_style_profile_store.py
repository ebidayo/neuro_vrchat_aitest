import pytest
import time
from core.memory.speaker_store import SpeakerStore

def test_update_and_get_style_profile(tmp_path):
    db = tmp_path / 'test.sqlite'
    store = SpeakerStore(str(db))
    k = 'user1'
    now = 1000
    f1 = {'top_tokens':[{'t':'まじ','c':2}], 'top_bigrams':[{'t':'それな','c':1}], 'filler':[{'t':'えっと','c':1}],
          'punct':{'q_rate':0.1,'ex_rate':0.2,'emoji_rate':0.0},
          'politeness':{'desu_masu':0.5,'da_dearu':0.5}, 'length':{'avg_chars':10}}
    store.update_style_profile(k, f1, now)
    prof = store.get_style_profile(k)
    assert prof['top_tokens'][0]['t'] == 'まじ'
    assert prof['top_bigrams'][0]['t'] == 'それな'
    assert prof['filler'][0]['t'] == 'えっと'
    # マージ
    f2 = {'top_tokens':[{'t':'まじ','c':3},{'t':'やば','c':2}], 'top_bigrams':[{'t':'それな','c':2}], 'filler':[{'t':'うーん','c':1}],
          'punct':{'q_rate':0.2,'ex_rate':0.1,'emoji_rate':0.1},
          'politeness':{'desu_masu':0.2,'da_dearu':0.8}, 'length':{'avg_chars':20}}
    store.update_style_profile(k, f2, now+10)
    prof2 = store.get_style_profile(k)
    assert any(t['t']=='やば' for t in prof2['top_tokens'])
    assert prof2['top_bigrams'][0]['t'] == 'それな'
    assert any(f['t']=='うーん' for f in prof2['filler'])
    # 上位K
    many = {'top_tokens':[{'t':str(i),'c':1} for i in range(30)], 'top_bigrams':[], 'filler':[],
            'punct':{'q_rate':0,'ex_rate':0,'emoji_rate':0}, 'politeness':{'desu_masu':0,'da_dearu':0}, 'length':{'avg_chars':0}}
    store.update_style_profile(k, many, now+20)
    prof3 = store.get_style_profile(k)
    assert len(prof3['top_tokens']) <= 20
    # 例外握り
    assert store.get_style_profile('no_such') is None
