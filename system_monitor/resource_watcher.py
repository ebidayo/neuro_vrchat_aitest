import time
import logging
from system_monitor.resource_probe import probe_resources
from system_monitor.resource_evaluator import evaluate_resource_state

class ResourceWatcher:
    def __init__(self, warn=0.75, danger=0.90, cooldown=90):
        self.last_level = "ok"
        self.last_emit_ts = 0.0
        self.warn = warn
        self.danger = danger
        self.cooldown = cooldown  # seconds
        self.last_dominant = None
        self.last_danger = 0.0

    def tick(self, now_ts=None):
        """
        Call periodically. Returns speech string if should emit, else None.
        Fail-soft: never raises.
        """
        try:
            now = now_ts if now_ts is not None else time.time()
            metrics = probe_resources()
            state = evaluate_resource_state(metrics)
            danger = state['danger']
            dominant = state['dominant']
            # Determine level
            level = "ok"
            if danger >= self.danger:
                level = "danger"
            elif danger >= self.warn:
                level = "warn"
            # Only emit if level worsened or (recovering and cooldown passed)
            emit = False
            msg = None
            if level == "danger" and (self.last_level != "danger"):
                emit = True
                msg = self._danger_message(dominant)
            elif level == "warn" and self.last_level == "ok":
                emit = True
                msg = self._warn_message(dominant)
            elif level == "ok" and self.last_level in ("warn","danger") and (now - self.last_emit_ts > self.cooldown):
                emit = True
                msg = self._recovery_message()
            if emit and msg:
                self.last_emit_ts = now
                self.last_level = level
                self.last_dominant = dominant
                self.last_danger = danger
                return msg
            # Always update state
            self.last_level = level
            self.last_dominant = dominant
            self.last_danger = danger
        except Exception as e:
            logging.debug(f"ResourceWatcher.tick fail-soft: {e}")
        return None

    def _danger_message(self, dominant):
        if dominant == "cpu":
            return "ちょっとCPUがやばいかも"
        if dominant == "ram":
            return "メモリきつそうだね"
        if dominant == "gpu":
            return "GPUが苦しそう"
        if dominant == "vram":
            return "VRAMが限界かも"
        return "リソースが厳しいかも"

    def _warn_message(self, dominant):
        if dominant == "cpu":
            return "CPU負荷が高めかも"
        if dominant == "ram":
            return "メモリ使用率が高いよ"
        if dominant == "gpu":
            return "GPU負荷が高いかも"
        if dominant == "vram":
            return "VRAM使用率が高いよ"
        return "リソース使用率が高いかも"

    def _recovery_message(self):
        return "リソース状態が落ち着いたみたい"
