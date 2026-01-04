"""OSC client (python-osc required).

Sends only numeric avatar parameters under the configured prefix and enforces rate limiting.
Provides a helper to send chatbox input for visible text (chatbox strings are NOT sent as avatar params).
"""
import logging
import time
from typing import Dict, Any

logger = logging.getLogger(__name__)

# python-osc may not be installed in all dev environments; provide a safe local fallback
try:
    from pythonosc.udp_client import SimpleUDPClient  # type: ignore
    _HAS_PYOSC = True
except Exception:
    _HAS_PYOSC = False
    class SimpleUDPClient:
        def __init__(self, ip, port):
            self.ip = ip
            self.port = port
        def send_message(self, address, value):
            logger.info("(fallback) OSC -> %s : %r", address, value)


class OscClient:
    def __init__(self, ip: str = "127.0.0.1", port: int = 9000, prefix: str = "/avatar/parameters", max_hz: float = 10.0):
        self.ip = ip
        self.port = port
        self.prefix = prefix.rstrip("/")
        self.max_hz = max_hz
        self._min_interval = 1.0 / max_hz if max_hz > 0 else 0
        self._last_send_time = 0.0
        self._last_sent: Dict[str, Any] = {}
        self._client = SimpleUDPClient(ip, port)
        logger.debug("OscClient initialized to %s:%s prefix=%s max_hz=%.1f", ip, port, self.prefix, max_hz)

    def _can_send(self) -> bool:
        now = time.time()
        if self._min_interval and (now - self._last_send_time) < self._min_interval:
            logger.debug("Rate limit: %.3fs remaining", self._min_interval - (now - self._last_send_time))
            return False
        return True

    def send_avatar_params(self, params: Dict[str, Any]) -> None:
        """Send only numeric diffs to /avatar/parameters/<name>.

        - params: mapping param_name->numeric (int/float/bool)
        - ignores non-numeric values
        """
        now = time.time()
        if not self._can_send():
            return

        # filter non-numeric
        numeric = {}
        for k, v in params.items():
            if isinstance(v, (int, float, bool)):
                numeric[k] = v
            else:
                try:
                    # try to coerce
                    numeric[k] = float(v)
                except Exception:
                    logger.warning("Skipping non-numeric param %s=%r", k, v)

        diffs = {k: v for k, v in numeric.items() if self._last_sent.get(k) != v}
        if not diffs:
            logger.debug("No numeric diffs to send")
            return

        try:
            for k, v in diffs.items():
                address = f"{self.prefix}/{k}"
                self._client.send_message(address, v)
            self._last_sent.update(diffs)
            self._last_send_time = now
            logger.info("Sent avatar params diffs: %s", diffs)
        except Exception:
            logger.exception("Failed sending avatar params")

    def send_chatbox(self, text: str, send_immediately: bool = True, notify: bool = True) -> None:
        """Send a string to the chatbox input (does not update avatar params).

        VRChat expects three arguments for `/chatbox/input`: [text, send_immediately, notify/message_complete].
        """
        try:
            payload = [str(text), bool(send_immediately), bool(notify)]
            self._client.send_message("/chatbox/input", payload)
            logger.info("Sent chatbox text (send_immediately=%s notify=%s)", send_immediately, notify)
        except Exception:
            logger.exception("Failed sending chatbox text")


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG)
    c = OscClient()
    c.send_avatar_params({"Emotion": 5, "TalkSpeed": 0.6})
    c.send_chatbox("Test chat message")
