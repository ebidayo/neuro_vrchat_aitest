import pytest
from core.kb_lookup import KBLookup

class DummyResp:
    def __init__(self, text='', status_code=200, json_data=None):
        self.text = text
        self.status_code = status_code
        self._json = json_data or {}
    def json(self):
        return self._json

class DummyHttp:
    def __init__(self, text='', json_data=None):
        self.text = text
        self.json_data = json_data
        self.calls = []
    def get(self, url, timeout=6):
        self.calls.append(url)
        if 'wikipedia' in url:
            return DummyResp(json_data={
                'extract': 'これはテストの要約です。',
                'content_urls': {'desktop': {'page': url}}
            })
        return DummyResp(text=self.text)

class DummyStore:
    def __init__(self):
        self._conn = self
        self.saved = []
    def execute(self, *a, **k):
        self.saved.append(a)
        return self
    def commit(self):
        pass

def test_kb_lookup_wikipedia():
    config = {'allow_wikipedia': True}
    store = DummyStore()
    http = DummyHttp()
    kb = KBLookup(config, store, http, logger=None)
    res = kb.lookup('テスト')
    assert res and 'wikipedia' in res['source'] and '要約' in res['snippet']

def test_kb_lookup_user_url():
    config = {'allow_user_urls': True, 'allow_niconico_dic_only_if_user_url': True}
    store = DummyStore()
    http = DummyHttp(text='<title>ユーザー記事</title>')
    kb = KBLookup(config, store, http, logger=None)
    res = kb.lookup('foo', user_url='http://dic.nicovideo.jp/test')
    assert res and 'niconico' in res['source'] and 'ユーザー記事' in res['snippet']

def test_kb_lookup_failsoft():
    class BadHttp:
        def get(self, url, timeout=6):
            raise Exception('fail')
    config = {'allow_wikipedia': True}
    store = DummyStore()
    kb = KBLookup(config, store, BadHttp(), logger=None)
    res = kb.lookup('テスト')
    assert res is None
