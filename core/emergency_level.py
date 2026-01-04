# core/emergency_level.py
"""
Adapter for emergency/disaster detection using existing ResourceWatcher, SelfRegulator, and disaster_watch.
"""
def get_emergency_level(context):
    """
    Returns: "none" | "emergency" | "disaster"
    """
    try:
        # Disaster-level: disaster_watch (if available)
        dw = context.get("disaster_watch")
        if dw and getattr(dw, "active", False):
            return "disaster"
    except Exception:
        pass
    try:
        # Emergency-level: resource danger or error burst
        rw = context.get("resource_watcher")
        cfg = context.get("cfg", {})
        level = cfg.get("emergency_chat_resource_level", "danger")
        if rw and getattr(rw, "last_level", None) == level:
            return "emergency"
    except Exception:
        pass
    try:
        # Emergency-level: error burst
        error_burst = context.get("error_burst")
        now = context.get("now")
        if error_burst and now and error_burst.is_burst(now):
            return "emergency"
    except Exception:
        pass
    return "none"
