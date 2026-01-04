import time
import hashlib

class KBLookup:
    def __init__(self, config, store, http_client, logger):
        self.config = config
        self.store = store
        self.http_client = http_client
        self.logger = logger

    def lookup(self, query, user_url=None):
        from core.content_item import build_content_item
        now = int(time.time())
        source = None
        url = None
        snippet = None
        title = None
        # user_url優先
        if user_url and self.config.get('allow_user_urls', True):
            url = user_url
            if 'nicovideo.jp' in url or 'dic.nicovideo.jp' in url:
                if not self.config.get('allow_niconico_dic_only_if_user_url', True):
                    return None
                source = 'niconico'
            else:
                source = 'user_url'
            try:
                resp = self.http_client.get(url, timeout=6)
                if resp.status_code != 200:
                    return None
                text = resp.text
                title = ''
                import re
                m = re.search(r'<title>(.*?)</title>', text, re.I)
                if m:
                    title = m.group(1)
                snippet = (title or text[:100])[:180]
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"KBLookup user_url error: {e}")
                return None
        elif self.config.get('allow_wikipedia', True):
            # Wikipedia API
            source = 'wikipedia'
            url = f'https://ja.wikipedia.org/api/rest_v1/page/summary/{query}'
            try:
                resp = self.http_client.get(url, timeout=6)
                if resp.status_code != 200:
                    return None
                data = resp.json()
                snippet = data.get('extract', '')[:200]
                url = data.get('content_urls', {}).get('desktop', {}).get('page', url)
                title = data.get('title', query)
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"KBLookup wikipedia error: {e}")
                return None
        else:
            return None
        # DB保存
        try:
            id_ = hashlib.sha1((source + url + query).encode('utf-8')).hexdigest()
            self.store._conn.execute(
                "REPLACE INTO kb_snippets (id, source, query, url, fetched_ts, snippet) VALUES (?,?,?,?,?,?)",
                (id_, source, query, url, now, snippet)
            )
            self.store._conn.commit()
        except Exception as e:
            if self.logger:
                self.logger.warning(f"kb_snippets DB failed: {e}")
        # ContentItem生成
        try:
            item = build_content_item(
                kind="kb",
                source=source,
                title=title or query,
                url=url,
                summary=snippet,
                published_ts=now,
                fetched_ts=now,
                query=query
            )
            # 既存互換キーも維持
            item["snippet"] = snippet
            return item
        except Exception as e:
            if self.logger:
                self.logger.warning(f"ContentItem build failed: {e}")
            return {'source': source, 'url': url, 'snippet': snippet}
