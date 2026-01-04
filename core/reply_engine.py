"""Simple rule-based reply generator.

- Class: ReplyEngine(cfg: dict, seed: Optional[int]=None)
- Method: generate(text: str, now: Optional[float]=None) -> str

Behavior:
- Classifies text into: question, emotion, greeting, other
- Uses templated replies (short ack + concrete mention + a question)
- Avoids immediate repetition of identical replies (history-based)
- Uses only standard library
"""
from typing import Optional, Dict, Any, List, Tuple
import time
import random
import logging

logger = logging.getLogger(__name__)

class ReplyEngine:
    def __init__(self, cfg: Optional[Dict[str, Any]] = None, seed: Optional[int] = None):
        try:
            cfg = cfg or {}
            self._rng = random.Random(seed)
            self.history_size = int(cfg.get("history_size", 50))
            self.repeat_gap = float(cfg.get("repeat_gap_sec", 30.0))

            # templates per class
            self.templates = {
                "question": [
                    "そうなんですね、ところで{}についてどう思いますか？",
                    "興味深いです。{}についてもう少し詳しく教えてもらえますか？",
                    "なるほど。{}の点で具体的にはどうですか？",
                ],
                "emotion": [
                    "それは大変ですね。まずは{}について大丈夫ですか？",
                    "つらい時はありますよね。{}について誰かに頼めますか？",
                    "分かります。特に{}はどう対処していますか？",
                ],
                "greeting": [
                    "こんにちは！{}は今日どうですか？",
                    "はじめまして。{}について少し教えてくださいませんか？",
                    "やあ！{}、今日はどんな感じ？",
                ],
                "other": [
                    "そうなんですね、ちなみに{}って具体的にはどういうことですか？",
                    "面白いですね。{}についてもう少し聞かせてください。",
                    "なるほど、{}に関して何が一番気になりますか？",
                ]
            }

            self._history: List[Tuple[float, str]] = []  # list of (ts, reply_text)
        except Exception:
            logger.exception("ReplyEngine init failed; using defaults")
            self._rng = random.Random(seed)
            self.templates = {
                "other": ["そうなんですね、もう少し詳しく聞かせてください。"]
            }
            self._history = []
            self.history_size = 50
            self.repeat_gap = 30.0

    def _trim_history(self):
        if len(self._history) > self.history_size:
            self._history = self._history[-self.history_size:]

    def _classify(self, text: str) -> str:
        t = text.strip().lower()
        if "?" in t or "？" in text:
            return "question"
        emotive = ["やばい", "無理", "最高", "つらい", "悲しい", "嬉しい", "助けて"]
        for w in emotive:
            if w in text:
                return "emotion"
        greetings = ["こんにちは", "おはよう", "こんばんは", "はじめまして", "こんにちは"]
        for g in greetings:
            if g in text:
                return "greeting"
        return "other"

    def _extract_concrete(self, text: str) -> str:
        # crude extraction: pick a token of length >=2 or take first 6 chars
        tokens = [tok for tok in ''.join(ch if ch.isalnum() else ' ' for ch in text).split() if len(tok) >= 2]
        if tokens:
            # pick the most informative: longest
            tok = max(tokens, key=len)
            return tok[:12]
        return text[:12]

    def generate(self, text: str, now: Optional[float]=None) -> str:
        try:
            if not text:
                return "そうなんですね、もう少し詳しく聞かせてください。"
            if now is None:
                now = time.time()
            cls = self._classify(text)
            concrete = self._extract_concrete(text)

            # pick template that hasn't been used recently
            candidates = list(self.templates.get(cls, []) or self.templates.get("other", []))

            # defense: ensure candidates exist
            if not candidates:
                candidates = ["そうなんですね、もう少し詳しく聞かせてください。"]

            recent_texts = set([t for ts, t in self._history if now - ts < self.repeat_gap])

            chosen = None
            for tmpl in self._rng.sample(candidates, k=len(candidates)):
                reply = tmpl.format(concrete)
                if reply not in recent_texts and (not self._history or self._history[-1][1] != reply):
                    chosen = reply
                    break

            if chosen is None:
                # relax: allow repeating after checking not exact last twice
                chosen = candidates[self._rng.randrange(len(candidates))].format(concrete)

            # record history
            self._history.append((now, chosen))
            self._trim_history()
            return chosen
        except Exception:
            logger.exception("ReplyEngine.generate failed; returning safe fallback")
            return "なるほど、詳しく聞かせてください。"
