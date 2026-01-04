import math

from core.alert_engine import build_alert_speech_plan


def _chunks(plan):
    return plan.get("speech_plan") or []


def test_tsunami_inserts_geo_chunks_and_disclaimer():
    ev = {
        "type": "tsunami",
        "severity": 9,
        "event_time": 1700000000.0,
        "source": "DUMMY",
        "region_code": "dummy",
        "message": "Tsunami warning",
        "alert_event_id": "DUMMY|2026-01-01T00:00:00Z|dummy|tsunami",
        "update_seq": 1,
    }
    scalars = {"valence": 0.0, "arousal": 0.2, "confidence": 0.4, "glitch": 0.2, "curiosity": 0.2, "social_pressure": 0.2}
    user_loc = {"lat": 35.681236, "lon": 139.767125, "label": "Tokyo assumed"}

    plan = build_alert_speech_plan(ev, scalars, user_loc=user_loc, is_update=False, is_clear=False)
    sp = _chunks(plan)
    assert len(sp) >= 3  # alert + action + disclaimer 以上

    # disclaimer present
    assert any(c.get("type") == "disclaimer" for c in sp)

    # geo chunk contains km text
    assert any(("km" in (c.get("text") or "")) for c in sp)

    # OSC contains ALERT guidance somewhere
    osc_chunks = [c for c in sp if isinstance(c.get("osc"), dict)]
    assert len(osc_chunks) > 0
    assert any(
        (c["osc"].get("N_State") == "ALERT"
         and float(c["osc"].get("N_Arousal", 0.0)) >= 0.85
         and float(c["osc"].get("N_Look", 0.0)) >= 0.9)
        for c in osc_chunks
    )


def test_tsunami_override_distance_is_used():
    ev = {
        "type": "tsunami",
        "severity": 9,
        "event_time": 1700000000.0,
        "source": "DUMMY",
        "region_code": "dummy",
        "message": "Tsunami warning",
        "alert_event_id": "DUMMY|2026-01-01T00:00:00Z|dummy|tsunami",
        "update_seq": 1,
    }
    scalars = {"valence": 0.0, "arousal": 0.2, "confidence": 0.4, "glitch": 0.0, "curiosity": 0.2, "social_pressure": 0.2}
    user_loc = {"coast_distance_km": 12.5}

    plan = build_alert_speech_plan(ev, scalars, user_loc=user_loc, is_update=False, is_clear=False)
    sp = _chunks(plan)
    assert any(("12" in (c.get("text") or "")) for c in sp), "override distance should appear in some geo text"
