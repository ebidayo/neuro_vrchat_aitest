"""StarterEngine: selects idle starter phrases with simple anti-repeat logic.

Behavior:
- Supports simple list (starter_cfg['starters']) or categorized dict (starter_cfg['categorized']).
- Keeps history of (ts, category, text).
- Respects min_repeat_gap_sec and avoid_same_category_last_n.
- Gradually relaxes constraints if no candidate remains.
- Safe defaults and never raises exceptions.
"""
from typing import Optional, Dict, Any, List, Tuple
import time
import random
import logging

logger = logging.getLogger(__name__)

class StarterEngine:
    def __init__(self, starter_cfg: Dict[str, Any], seed: Optional[int] = None):
        try:
            self.cfg = starter_cfg or {}
            self.notify = bool(self.cfg.get("notify", False))
            self.history_size = int(self.cfg.get("history_size", 100))
            self.min_repeat_gap_sec = float(self.cfg.get("min_repeat_gap_sec", 120.0))
            self.avoid_same_category_last_n = int(self.cfg.get("avoid_same_category_last_n", 3))

            self._rng = random.Random(seed)

            self._items: List[Tuple[str, str, float]] = []  # list of (category, text, cat_weight)

            categorized = self.cfg.get("categorized")
            if categorized and isinstance(categorized, dict):
                for cat, info in categorized.items():
                    try:
                        weight = float(info.get("weight", 1.0))
                        items = info.get("items", []) or []
                        for it in items:
                            if isinstance(it, str) and it.strip():
                                self._items.append((cat, it.strip(), weight))
                    except Exception:
                        continue
            # backward-compatible simple list
            simple = self.cfg.get("starters")
            if simple and isinstance(simple, list):
                for it in simple:
                    if isinstance(it, str) and it.strip():
                        self._items.append(("misc", it.strip(), 1.0))

            # fallback items if none
            if not self._items:
                self._items = [("misc", "すみません、少し話してもいいですか？", 1.0), ("misc", "ちょっとお時間いいですか？", 1.0)]

            self._history: List[Tuple[float, str, str]] = []  # list of (ts, category, text)
        except Exception:
            logger.exception("StarterEngine init failed; using safe defaults")
            self.cfg = starter_cfg or {}
            self.notify = False
            self.history_size = 100
            self.min_repeat_gap_sec = 120.0
            self.avoid_same_category_last_n = 3
            self._rng = random.Random(seed)
            self._items = [("misc", "すみません、少し話してもいいですか？", 1.0), ("misc", "ちょっとお時間いいですか？", 1.0)]
            self._history = []

    def _trim_history(self):
        if len(self._history) > self.history_size:
            self._history = self._history[-self.history_size:]

    def choose(self, now: Optional[float] = None, mood: Optional[Dict[str, Any]] = None) -> str:
        try:
            if now is None:
                now = time.time()

            # Build list of candidate indices
            candidates = list(range(len(self._items)))

            # helper to check min_repeat_gap
            def allowed_by_gap(idx: int) -> bool:
                _, text, _ = self._items[idx]
                for ts, _, t in reversed(self._history):
                    if t == text:
                        if now - ts < self.min_repeat_gap_sec:
                            return False
                        else:
                            return True
                return True

            # helper to check avoid_same_category_last_n
            avoid_cats = [cat for _, cat, _t in [(h[0], h[1], h[2]) for h in self._history[-self.avoid_same_category_last_n:]]] if self.avoid_same_category_last_n > 0 else []
            avoid_cats = []
            if self.avoid_same_category_last_n > 0:
                avoid_cats = [entry[1] for entry in self._history[-self.avoid_same_category_last_n:]]

            def allowed_by_category(idx: int) -> bool:
                cat, _, _ = self._items[idx]
                return cat not in avoid_cats

            # Apply filters progressively
            filters = [lambda i: allowed_by_gap(i) and allowed_by_category(i),  # strict
                       lambda i: allowed_by_gap(i),  # relax category avoidance
                       lambda i: True]  # relax gap as well

            chosen_text = None
            chosen_cat = None
            for f in filters:
                filtered = [i for i in candidates if f(i)]
                if filtered:
                    # build weights using categories weights
                    weights = [self._items[i][2] for i in filtered]
                    idx = self._rng.choices(filtered, weights=weights, k=1)[0]
                    chosen_cat, chosen_text, _ = self._items[idx]
                    break

            # final fallback: if still none, pick first safe
            if chosen_text is None:
                chosen_cat, chosen_text, _ = self._items[0]

            # ensure not same as very last entry
            if self._history and self._history[-1][2] == chosen_text:
                # pick alternative if available
                for i in range(len(self._items)):
                    cat_i, text_i, _ = self._items[(i + 1) % len(self._items)]
                    if text_i != chosen_text:
                        chosen_cat, chosen_text = cat_i, text_i
                        break

            # record history
            self._history.append((now, chosen_cat, chosen_text))
            self._trim_history()
            return chosen_text
        except Exception:
            logger.exception("StarterEngine.choose failed; returning safe fallback")
            try:
                return self._items[0][1]
            except Exception:
                return "ちょっとお話いいですか？"
