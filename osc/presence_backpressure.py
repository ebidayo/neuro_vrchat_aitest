def ewma(latencies, alpha=0.3):
    if not latencies:
        return 0.0
    avg = latencies[0]
    for l in latencies[1:]:
        avg = alpha * l + (1 - alpha) * avg
    return avg

class PresenceBackpressure:
    def __init__(self, config):
        self.cfg = config
        self.downgrade_ms = int(config.get('osc_latency_downgrade_ms', 35))
        self.recover_ms = int(config.get('osc_latency_recover_ms', 20))
        self.danger_hz = float(config.get('osc_face_update_hz_danger', 0.05))
        self.normal_hz = float(config.get('idle_face_drift_tick_hz', 0.2))
        self.latencies = []
        self.update_hz = self.normal_hz
        self.last_recover = 0.0
    def add_latency(self, ms):
        self.latencies.append(ms)
        if len(self.latencies) > 30:
            self.latencies = self.latencies[-30:]
    def tick(self, now):
        avg = ewma(self.latencies)
        if avg > self.downgrade_ms:
            self.update_hz = self.danger_hz
            self.last_recover = now
        elif avg < self.recover_ms and now - self.last_recover > 30:
            self.update_hz = self.normal_hz
        return self.update_hz
