import re
import time
import threading
import json
from typing import List, Optional

# --- LexicalPattern definition ---
class LexicalPattern:
    def __init__(self, surface_form: str, category: str, register: str, occurrence_weight: float, last_seen_ts: float):
        self.surface_form = surface_form
        self.category = category  # 'net' or 'normal'
        self.register = register  # 'casual' or 'neutral'
        self.occurrence_weight = occurrence_weight
        self.last_seen_ts = last_seen_ts
    def to_dict(self):
        return {
            'surface_form': self.surface_form,
            'category': self.category,
            'register': self.register,
            'occurrence_weight': self.occurrence_weight,
            'last_seen_ts': self.last_seen_ts,
        }
    @staticmethod
    def from_dict(d):
        return LexicalPattern(
            d['surface_form'], d['category'], d['register'], d['occurrence_weight'], d['last_seen_ts']
        )

# --- Fail-soft storage ---
class _PatternStore:
    def __init__(self, path='twitter_lexical_patterns.json'):
        self.path = path
        self.lock = threading.Lock()
        self.patterns = self._load()
    def _load(self):
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                arr = json.load(f)
            return [LexicalPattern.from_dict(x) for x in arr]
        except Exception:
            return []
    def save(self):
        try:
            with self.lock:
                arr = [p.to_dict() for p in self.patterns]
                with open(self.path, 'w', encoding='utf-8') as f:
                    json.dump(arr, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    def get_all(self):
        return list(self.patterns)
    def update(self, new_patterns: List[LexicalPattern]):
        with self.lock:
            self.patterns = new_patterns
            self.save()

# --- Filtering rules ---
_URL_RE = re.compile(r'https?://|www\.')
_RT_RE = re.compile(r'(^|\s)RT[ :]|引用|QT[ :]', re.IGNORECASE)
_HASHTAG_RE = re.compile(r'#\w+')
_NON_JP_RE = re.compile(r'^[\x00-\x7F\s]+$')
_POLITICS = ['選挙', '政治', '政党', '首相', '大統領', '宗教', '信仰', '天皇', '戦争', '平和', '右翼', '左翼']
_INSULTS = ['死ね', 'バカ', 'アホ', 'うざい', '消えろ', '黙れ', 'クズ', '馬鹿', '殺す', '訴える', 'やれ', '命令']

# --- Extraction rules ---
_NET_WORDS = [
    '草', 'w', '乙', 'ググれ', 'オワコン', '神', 'ワロタ', 'ガチ', 'エモい', 'バズる', 'リプ', 'DM', 'TL', '晒し', '炎上',
    'リア充', '黒歴史', 'メンヘラ', '推し', '沼', '案件', '垢', '鍵垢', 'bot', 'ROM専', 'リムる', 'フォロバ', 'サブ垢',
    'TL', 'バ美肉', 'オタク', '厨', '民', '界隈', '案件', 'バレ', '晒し', '草生える', 'つらみ', 'やらかし', '案件',
]

# --- Main learner class ---
class TwitterLexicalLearner:
    def __init__(self, store_path=None):
        self.store = _PatternStore(store_path or 'twitter_lexical_patterns.json')
        self.decay_rate = 0.95
        self.net_threshold = 3.0
        self.normal_threshold = 10.0
        self.min_length = 5
        self.max_length = 140
    def process_tweet(self, text: str, ts: Optional[float] = None):
        try:
            if not self._filter(text):
                return
            ts = ts or time.time()
            patterns = self._extract_patterns(text, ts)
            if not patterns:
                return
            all_patterns = self.store.get_all()
            updated = self._merge_patterns(all_patterns, patterns, ts)
            self.store.update(updated)
        except Exception:
            pass
    def _filter(self, text: str) -> bool:
        if not text or len(text) < self.min_length or len(text) > self.max_length:
            return False
        if _NON_JP_RE.match(text):
            return False
        if _URL_RE.search(text):
            return False
        if _RT_RE.search(text):
            return False
        if len(_HASHTAG_RE.findall(text)) > 2:
            return False
        if any(w in text for w in _POLITICS):
            return False
        if any(w in text for w in _INSULTS):
            return False
        return True
    def _extract_patterns(self, text: str, ts: float) -> List[LexicalPattern]:
        results = []
        # Extract net words
        for w in _NET_WORDS:
            if w in text:
                results.append(LexicalPattern(w, 'net', 'casual', 1.0, ts))
        # Extract short endings/fillers (ex: 〜だよね, 〜かな, 〜かも, 〜www)
        endings = re.findall(r'(だよね|だよ|かな|かも|かもね|かも？|かもw+|www+|w+|だな|だぜ|だし|じゃん|じゃね|じゃね？|だっけ|だって|だろ|だろう|だわ|だす|だぬ|だお|だおー|だおw+|だおwww+)', text)
        for e in endings:
            results.append(LexicalPattern(e, 'net' if e in _NET_WORDS or 'w' in e else 'normal', 'casual', 1.0, ts))
        # Extract short phrases (up to 8 chars, not full sentence)
        phrases = re.findall(r'([ぁ-んァ-ン一-龥a-zA-Z0-9]{2,8})', text)
        for p in phrases:
            if p not in _NET_WORDS and len(p) < 9:
                results.append(LexicalPattern(p, 'normal', 'neutral', 0.3, ts))
        return results
    def _merge_patterns(self, all_patterns, new_patterns, now):
        pat_map = {(p.surface_form, p.category, p.register): p for p in all_patterns}
        for np in new_patterns:
            key = (np.surface_form, np.category, np.register)
            if key in pat_map:
                pat_map[key].occurrence_weight += np.occurrence_weight
                pat_map[key].last_seen_ts = now
            else:
                pat_map[key] = np
        # Decay and prune
        keep = []
        for p in pat_map.values():
            days = max(0, (now - p.last_seen_ts) / 86400)
            p.occurrence_weight *= self.decay_rate ** days
            if (p.category == 'net' and p.occurrence_weight >= self.net_threshold) or \
               (p.category == 'normal' and p.occurrence_weight >= self.normal_threshold):
                keep.append(p)
        return keep
    def get_candidates(self, mode='TALK_PRIMARY', context='casual') -> List[LexicalPattern]:
        try:
            if mode != 'TALK_PRIMARY' or context not in ('casual', 'neutral'):
                return []
            pats = self.store.get_all()
            # Max 15% usage, no連続net
            net_used = False
            result = []
            for p in pats:
                if p.category == 'net':
                    if net_used:
                        continue
                    net_used = True
                if random.random() <= 0.15:
                    result.append(p)
            return result
        except Exception:
            return []
