import re
import unicodedata
from typing import List, Dict
import json

STOPWORDS = set([
    "これ", "それ", "あれ", "ここ", "そこ", "あそこ", "こと", "もの", "ため", "よう", "ところ", "ので", "でも", "から", "ので", "です", "ます"
])
FILLER_WORDS = ["えっと", "なんか", "その", "てか", "まぁ", "まじ", "ガチ", "うーん", "あの", "ほら", "ええと"]

# --- 1. normalize_text ---
def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize('NFKC', text)
    text = text.strip()
    text = text.replace('\n', ' ').replace('\t', ' ')
    text = re.sub(r'\s+', ' ', text)
    # URL
    text = re.sub(r'https?://\S+|www\.\S+', '<url>', text)
    # mention
    text = re.sub(r'@\w+', '<mention>', text)
    # hashtag
    text = re.sub(r'#\w+', '<hashtag>', text)
    # 連続数字
    text = re.sub(r'\d{2,}', '<num>', text)
    # w連打（3文字以上はwwwに）
    text = re.sub(r'w{3,}', 'www', text)
    # 記号圧縮
    text = re.sub(r'!{2,}', '!', text)
    text = re.sub(r'！{2,}', '！', text)
    text = re.sub(r'\?{2,}', '?', text)
    text = re.sub(r'？{2,}', '？', text)
    text = re.sub(r'(…|\.{3,})', '…', text)
    text = text.strip()
    return text[:5000]

# --- 2. tokenize_ja_simple ---
def tokenize_ja_simple(text: str) -> List[str]:
    if not text:
        return []
    # normalize_text前提
    PATTERN = r'(<url>|<mention>|<hashtag>|<num>|[一-龥ぁ-ゟァ-ヿー]+|[A-Za-z]+|\d+|w+|…|[!?]+)'
    tokens = re.findall(PATTERN, text)
    # スラング分割: まじやばい→[まじ,やばい] など
    SPLIT_WORDS = ["まじ", "やばい", "やば", "それな"]
    out = []
    for t in tokens:
        # まじやばい→[まじ,やばい]、それなたしかに→[それな,たしかに]
        if t.startswith("まじ") and t != "まじ" and (t[len("まじ"):] in {"やばい","やば"}):
            out.append("まじ")
            out.append(t[len("まじ"):])
        elif t.startswith("それな") and t != "それな" and t[len("それな"):]:
            out.append("それな")
            out.append(t[len("それな"):])
        else:
            out.append(t)
    tokens = [t for t in out if t and t not in STOPWORDS and t.strip()]
    return tokens

# --- 3. extract_features ---
def extract_features(text: str) -> Dict:
    norm = normalize_text(text)
    tokens = tokenize_ja_simple(norm)
    # top_tokens: <URL>/<NUM>/<TAG>や記号以外、長さ1-6
    def is_candidate_token(t):
        if t in ('<url>', '<mention>', '<hashtag>', '<num>'):
            return False
        if re.match(r'^[!?…。、]+$', t):
            return False
        # 先頭大文字英単語や英単語4文字以上は除外
        if re.match(r'^[A-Z][a-z]{2,}$', t):
            return False
        if re.match(r'^[A-Za-z]{4,}$', t):
            return False
        # 全漢字2文字（人名等）を除外
        if re.match(r'^[一-龥]{2}$', t):
            return False
        return 1 <= len(t) <= 6
    token_counts = {}
    for t in tokens:
        if is_candidate_token(t):
            token_counts[t] = token_counts.get(t, 0) + 1
    top_tokens = sorted([{ "t": k, "c": v } for k, v in token_counts.items()], key=lambda x: (-x["c"], x["t"]))[:20]
    # filler: normalizeした上で前方一致
    filler_counts = {}
    for t in tokens:
        for f in FILLER_WORDS:
            if t.startswith(f):
                filler_counts[f] = filler_counts.get(f, 0) + 1
    filler = sorted([{ "t": k, "c": v } for k, v in filler_counts.items()], key=lambda x: (-x["c"], x["t"]))[:10]
    # bigrams: 記号以外の隣接ペア＋単体スラングも含める
    bigram_counts = {}
    cands = [t for t in tokens if is_candidate_token(t)]
    for i in range(len(cands)-1):
        bg = cands[i] + cands[i+1]
        if 2 <= len(bg) <= 8:
            bigram_counts[bg] = bigram_counts.get(bg, 0) + 1
    # スラング単体（例: それな）もbigram候補に
    for t in cands:
        if t in {"それな","まじ","やばい","やば"}:
            bigram_counts[t] = bigram_counts.get(t, 0) + 1
    top_bigrams = sorted([{ "t": k, "c": v } for k, v in bigram_counts.items()], key=lambda x: (-x["c"], x["t"]))[:20]
    # 文末スタイル
    desu_masu = sum(1 for t in tokens if t.endswith("です") or t.endswith("ます"))
    da_dearu = sum(1 for t in tokens if t.endswith("だ") or t.endswith("じゃん") or t.endswith("よね") or t.endswith("な"))
    total = max(1, len(tokens))
    # 句読点/？/！/emoji
    q_rate = norm.count('？')/total if total else 0
    ex_rate = norm.count('！')/total if total else 0
    emoji_rate = len(re.findall(r'[\U0001F600-\U0001F64F]', norm))/total if total else 0
    # 平均長
    avg_chars = sum(len(t) for t in tokens)/total if total else 0
    return {
        "top_tokens": top_tokens,
        "top_bigrams": top_bigrams,
        "filler": filler,
        "punct": {"q_rate": q_rate, "ex_rate": ex_rate, "emoji_rate": emoji_rate},
        "politeness": {"desu_masu": desu_masu/total, "da_dearu": da_dearu/total},
        "length": {"avg_chars": avg_chars}
    }
