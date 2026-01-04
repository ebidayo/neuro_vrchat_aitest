from neuro_vrchat_ai.core.state_machine import StateMachine, State

def test_alert_interrupt_applies_on_chunk_boundary():
    sm = StateMachine()

    # TALK 状態にする
    sm.state = State.TALK

    # ALERT を投げる（severity 高）
    alert = {
        "type": "tsunami",
        "severity": 9,
        "event_time": 1700000000.0,
        "source": "DUMMY",
        "region_code": "dummy",
        "message": "Tsunami warning",
        "alert_event_id": "TEST|2026|dummy|tsunami",
        "update_seq": 1,
    }

    sm.on_event("alert_new", alert)

    # まだ TALK のまま（即時割り込みしない）
    assert sm.state == State.TALK
    assert sm._pending_interrupt is not None

    # チャンク終了を通知
    sm.mark_speech_done()

    # ここで ALERT に遷移
    assert sm.state == State.ALERT
    assert sm._pending_interrupt is None
