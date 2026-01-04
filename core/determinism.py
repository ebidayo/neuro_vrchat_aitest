import time
import hashlib

class TimeProvider:
    def __init__(self, fixed_times=None):
        self.fixed_times = fixed_times or []
        self.idx = 0
    def now(self):
        if self.idx < len(self.fixed_times):
            t = self.fixed_times[self.idx]
            self.idx += 1
            return t
        return time.time()

class DeterministicRNG:
    def __init__(self, seed):
        self.seed = seed
        self.state = int(hashlib.sha256(str(seed).encode()).hexdigest(), 16) % (2**32)
    def rand(self):
        # xorshift32
        x = self.state
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= (x >> 17)
        x ^= (x << 5) & 0xFFFFFFFF
        self.state = x & 0xFFFFFFFF
        return (self.state % 10000) / 10000.0
    def randint(self, a, b):
        return a + int(self.rand() * (b - a + 1))
    def uniform(self, a, b):
        return a + (b - a) * self.rand()
