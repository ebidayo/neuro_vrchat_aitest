import re
from typing import Optional

def apply_style(text: str, profile: dict, budget: dict) -> str:
    if not profile or not isinstance(profile, dict):
        return text
    max_inserts = budget.get('max_inserts', 1)
    allow_filler = budget.get('allow_filler', True)
    allow_bigram = budget.get('allow_bigram', True)
    allow_token = budget.get('allow_token', True)
    inserted = 0
    out = text
    used = set()
    # 1. 文頭フィラー
    if allow_filler and profile.get('filler'):
        for f in profile['filler']:
            t = f['t']
            if t and t not in out and inserted < max_inserts:
                out = t + '、' + out
                used.add(t)
                inserted += 1
                break
    # 2. 文末タグ（bigram）
    if allow_bigram and profile.get('top_bigrams'):
        for b in profile['top_bigrams']:
            t = b['t']
            if t and t not in out and inserted < max_inserts:
                if len(out) > 8 and not re.search(r'[。！？?]$', out):
                    out = out + t
                    used.add(t)
                    inserted += 1
                    break
    # 3. 途中のtoken
    if allow_token and profile.get('top_tokens'):
        for tk in profile['top_tokens']:
            t = tk['t']
            if t and t not in out and inserted < max_inserts:
                # 挿入位置: 2文字目以降
                if len(out) > 4:
                    out = out[:2] + t + out[2:]
                    used.add(t)
                    inserted += 1
                    break
    # 末尾「？」は増やさない
    if out.count('？') > text.count('？'):
        out = out.replace('？', '', 1)
    return out
