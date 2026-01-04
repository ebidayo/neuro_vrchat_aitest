
import time
import xml.etree.ElementTree as ET
import hashlib
from core.content_item import build_content_item

class NewsWatcher:
    def __init__(self, feeds, poll_interval_sec, ttl_sec, cooldown_sec, store, http_client, logger):
        self.feeds = feeds
        self.poll_interval_sec = poll_interval_sec
        self.ttl_sec = ttl_sec
        self.cooldown_sec = cooldown_sec
        self.store = store
        self.http_client = http_client
        self.logger = logger
        self.last_poll_ts = 0
        self.topic_last_ts = {}
        self.seen_ids = set()



    def _make_topic_key(self, title):
        # 記号・空白除去、小文字化
        return ''.join(c for c in title.lower() if c.isalnum())

    def tick(self, now=None):
        now = now or time.time()
        if now - self.last_poll_ts < self.poll_interval_sec:
            return []
        self.last_poll_ts = now
        new_items = []
        for feed in self.feeds:
            try:
                resp = self.http_client.get(feed['url'], timeout=6)
                if resp.status_code != 200:
                    continue
                root = ET.fromstring(resp.text)
                for item in root.findall('.//item'):
                    title = item.findtext('title') or ''
                    url = item.findtext('link') or ''
                    pubdate = item.findtext('pubDate') or ''
                    # pubDateパース（RFC1123/2822形式→unixtime）
                    import email.utils
                    try:
                        published_ts = int(time.mktime(email.utils.parsedate(pubdate))) if pubdate else int(now)
                    except Exception:
                        published_ts = int(now)
                    topic_key = self._make_topic_key(title)
                    id_ = hashlib.sha1((feed['name'] + url).encode('utf-8')).hexdigest()
                    if id_ in self.seen_ids:
                        continue
                    # cooldown（同一topicの連続記事抑制: ただしID優先で一度だけ返す）
                    last = self.topic_last_ts.get(topic_key, 0)
                    if now - last < self.cooldown_sec:
                        continue
                    self.topic_last_ts[topic_key] = published_ts
                    self.seen_ids.add(id_)
                    summary = (title[:60] + '...') if len(title) > 60 else title
                    # DB保存
                    try:
                        self.store._conn.execute(
                            "REPLACE INTO news_items (id, source, title, url, published_ts, fetched_ts, summary, topic_key) VALUES (?,?,?,?,?,?,?,?)",
                            (id_, feed['name'], title, url, published_ts, int(now), summary, topic_key)
                        )
                        self.store._conn.commit()
                    except Exception as e:
                        if self.logger:
                            self.logger.warning(f"news_items DB failed: {e}")
                    # ContentItem生成
                    try:
                        item = build_content_item(
                            kind="news",
                            source=feed['name'],
                            title=title,
                            url=url,
                            summary=summary,
                            published_ts=published_ts,
                            fetched_ts=int(now)
                        )
                        new_items.append(item)
                    except Exception as e:
                        if self.logger:
                            self.logger.warning(f"ContentItem build failed: {e}")
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"NewsWatcher feed error: {e}")
        return new_items
