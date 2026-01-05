from typing import List, Optional
from .types import SpeechItem, SpeechMeta

class SpeechQueue:
    def __init__(self):
        self._queue: List[SpeechItem] = []
        self._active: Optional[SpeechItem] = None
        self._interrupted: List[SpeechItem] = []

    def submit(self, item: SpeechItem) -> None:
        meta = item.meta
        if meta.is_emergency:
            self.clear("emergency")
            self._queue.append(item)
            return
        if meta.can_interrupt and self._active:
            # Mark active as interrupted
            self._interrupted.append(self._active)
            if meta.allow_overlap:
                self._queue.insert(0, item)
            else:
                self._queue = [item]
            return
        self._queue.append(item)

    def submit_text(self, text, voice, prosody, meta, now_ms) -> SpeechItem:
        item = SpeechItem(text=text, voice=voice, prosody=prosody, meta=meta, created_at_ms=now_ms)
        self.submit(item)
        return item

    def pop_next(self, now_ms) -> Optional[SpeechItem]:
        if self._queue:
            item = self._queue.pop(0)
            self._active = item
            return item
        self._active = None
        return None

    def clear(self, reason: str) -> None:
        self._queue.clear()
        self._active = None
        self._interrupted.clear()
