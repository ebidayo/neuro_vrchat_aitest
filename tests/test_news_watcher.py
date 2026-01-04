import pytest
from core.news_watcher import NewsWatcher

class DummyResp:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code

class DummyHttp:
    def __init__(self, rss_text):
        self.rss_text = rss_text
        self.calls = 0
    def get(self, url, timeout=6):
        self.calls += 1
        return DummyResp(self.rss_text)

class DummyStore:
    def __init__(self):
        self._conn = self
        self.saved = []
    def execute(self, *a, **k):
        self.saved.append(a)
        return self
    def commit(self):
        pass

RSS = '''<rss><channel><item><title>テスト記事1</title><link>http://ex.com/1</link><pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate></item><item><title>テスト記事2</title><link>http://ex.com/2</link><pubDate>Mon, 01 Jan 2024 01:00:00 GMT</pubDate></item></channel></rss>'''

def test_news_watcher_tick():
    feeds = [{'name':'TestFeed','url':'http://dummy/rss'}]
    http = DummyHttp(RSS)
    store = DummyStore()
    logger = None
    nw = NewsWatcher(feeds, poll_interval_sec=0, ttl_sec=86400, cooldown_sec=0, store=store, http_client=http, logger=logger)
    items = nw.tick(now=10000)
    assert len(items) == 2
    assert items[0]['title'] == 'テスト記事1'
    # cooldown効く
    items2 = nw.tick(now=10001)
    assert items2 == []

def test_news_watcher_failsoft():
    feeds = [{'name':'TestFeed','url':'http://dummy/rss'}]
    class BadHttp:
        def get(self, url, timeout=6):
            raise Exception('fail')
    store = DummyStore()
    nw = NewsWatcher(feeds, poll_interval_sec=0, ttl_sec=86400, cooldown_sec=0, store=store, http_client=BadHttp(), logger=None)
    items = nw.tick(now=20000)
    assert items == []
