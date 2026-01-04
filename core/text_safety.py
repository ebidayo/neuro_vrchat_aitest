import re

def sanitize_for_storage(text: str) -> str:
    """
    決定的な正規化・PII/URL/mention/email/数字のマスク・長文クリップ。
    例外時は短縮版を返す。
    """
    try:
        if not isinstance(text, str):
            text = str(text)
        t = text
        # email（正規化前に文中部分置換）
        t = re.sub(r'[\w\.-]+@[\w\.-]+', '<email>', t)
        # normalize: 全角→半角, 改行→space, 連続space→1
        t = t.replace('\u3000', ' ').replace('\r', '').replace('\n', ' ')
        t = re.sub(r'\s+', ' ', t)
        # URL
        t = re.sub(r'https?://[\w/:%#\$&\?\(\)~\.=\+\-]+', '<url>', t)
        # mention
        t = re.sub(r'@[\w\-]+', '<mention>', t)
        # hashtag
        t = re.sub(r'#[\w\-]+', '<hashtag>', t)
        # 2桁以上の数字
        t = re.sub(r'\d{2,}', '<num>', t)
        # クリップ
        N = 500
        if len(t) > N:
            t = t[:N] + '...'
        return t
    except Exception:
        # fail-soft: 先頭100文字のみ返し、必ず'...'を付与
        s = str(text)
        if not s.endswith('...'):
            s = s[:100] + '...'
        else:
            # 既に...が付いている場合も100文字超ならクリップ
            if len(s) > 103:
                s = s[:100] + '...'
        return s
