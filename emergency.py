from dataclasses import dataclass
import hashlib

@dataclass(frozen=True)
class EmergencyDecision:
    should_alert: bool
    message_ja: str
    content_hash: str
    reason: str
    suppressed_by_cooldown: bool

def _normalize_message(msg: str) -> str:
    t = msg.strip()
    t = ' '.join(t.split())
    return t

def _hash_message(msg: str) -> str:
    return hashlib.sha1(msg.encode("utf-8")).hexdigest()

class EmergencyController:
    def __init__(self, cfg, clock, logger, beep_player=None):
        self.cfg = cfg or {}
        self.clock = clock
        self.logger = logger
        self.beep_player = beep_player
        self._last_alert_ts = None
        self._last_content_hash = None
        self._active_until_ts = None

    def is_enabled(self) -> bool:
        return bool(self.cfg.get("enabled", False))

    def is_active(self) -> bool:
        if not self.is_enabled():
            return False
        try:
            now = self.clock.now()
        except Exception:
            return False
        return self._active_until_ts is not None and now <= self._active_until_ts

    def should_suppress_stt(self) -> bool:
        return self.is_active()

    def should_suppress_opinion(self) -> bool:
        return self.is_active()

    def maybe_trigger(self, message_ja: str, *, reason: str) -> EmergencyDecision:
        try:
            if not self.is_enabled():
                return EmergencyDecision(False, "", "", reason, suppressed_by_cooldown=False)
            normalized = _normalize_message(message_ja)
            if normalized == "":
                return EmergencyDecision(False, "", "", reason, suppressed_by_cooldown=False)
            content_hash = _hash_message(normalized)
            cooldown = float(self.cfg.get("cooldown_sec", 10.0))
            hold = float(self.cfg.get("active_hold_sec", cooldown))
            now = self.clock.now()
            allow = False
            if self._last_alert_ts is None:
                allow = True
            else:
                dt = now - self._last_alert_ts
                if dt < cooldown:
                    allow = (content_hash != self._last_content_hash)
                else:
                    allow = True
            if allow:
                self._last_alert_ts = now
                self._last_content_hash = content_hash
                self._active_until_ts = now + hold
                # Beep (fail-soft)
                path = self.cfg.get("beep_wav_path", "")
                if self.beep_player and path:
                    try:
                        self.beep_player.play(path)
                    except Exception:
                        pass
                # Log (do not log full message)
                self.logger.info(f"EMERGENCY: reason={reason} hash={content_hash} bypass={allow and dt < cooldown if self._last_alert_ts else False}")
                return EmergencyDecision(True, normalized, content_hash, reason, suppressed_by_cooldown=False)
            else:
                # Optionally: keep _active_until_ts unchanged (minimal diff)
                return EmergencyDecision(False, normalized, content_hash, reason, suppressed_by_cooldown=True)
        except Exception:
            return EmergencyDecision(False, "", "", reason, suppressed_by_cooldown=False)

    def reset(self) -> None:
        self._last_alert_ts = None
        self._last_content_hash = None
        self._active_until_ts = None
