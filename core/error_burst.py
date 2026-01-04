# core/error_burst.py
from collections import deque

class ErrorBurst:
    def __init__(self, n, window_sec, time_provider):
        self.n = max(2, int(n))
        self.window = max(5, float(window_sec))
        self.tp = time_provider
        self.errors = deque()
    def record_error(self, now=None):
        if now is None:
            now = self.tp.now()
        self.errors.append(now)
        # Remove old
        while self.errors and now - self.errors[0] > self.window:
            self.errors.popleft()
    def is_burst(self, now=None):
        if now is None:
            now = self.tp.now()
        self.errors = deque([t for t in self.errors if now - t <= self.window])
        return len(self.errors) >= self.n
