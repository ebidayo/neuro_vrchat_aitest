"""Simple disaster watch placeholder.

Phase1: produces dummy events and provides an adapter interface for real sources.
- run_monitor(callback): runs in background and calls callback(event_dict) on notable events
- Event dict: {type:'earthquake'|'tsunami'|'update', severity:int, info: {...}}
"""
import asyncio
import logging
import random
import time
from typing import Callable, Dict, Any

logger = logging.getLogger(__name__)

async def run_dummy_monitor(cb: Callable[[Dict[str, Any]], None], interval: float = 15.0):
    """Periodically emits a dummy event with low probability to simulate alerts.

    Events include robust identifiers for v1.2: alert_event_id and update_seq.
    """
    from datetime import datetime, timezone

    async def _emit(ev: Dict[str, Any]):
        event_time = ev.get("timestamp", time.time())
        iso = datetime.fromtimestamp(event_time, tz=timezone.utc).isoformat()
        source = ev.get("source", "DUMMY")
        region = ev.get("region_code", "dummy")
        typ = ev.get("type", "unknown")
        alert_event_id = f"{source}|{iso}|{region}|{typ}"
        ev["alert_event_id"] = alert_event_id
        ev["event_time"] = event_time
        ev["source"] = source
        ev["region_code"] = region
        # single-shot dummy monitor: update_seq 1
        ev["update_seq"] = ev.get("update_seq", 1)
        # normalize message
        info = ev.get("info", {})
        ev["message"] = info.get("message", "")
        try:
            cb(ev)
        except Exception:
            logger.exception("Callback failed in disaster monitor")

    while True:
        await asyncio.sleep(interval)
        if random.random() < 0.15:
            # emit either earthquake or tsunami
            if random.random() < 0.2:
                base = {"type": "tsunami", "severity": 9, "info": {"message": "Tsunami advisory issued"}, "timestamp": time.time()}
            else:
                sev = random.randint(1, 7)
                base = {"type": "earthquake", "severity": sev, "info": {"message": f"Shake level {sev}"}, "timestamp": time.time()}
            logger.info("Disaster monitor: emitting event %s", base)
            await _emit(base)
