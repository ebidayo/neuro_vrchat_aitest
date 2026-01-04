# CHANGELOG

## 2026-01-05
- Initial functional completion: memory/content tracking, privacy, decay, cleanup, source request, display, OSC/valence/interest sync, local TTS, prosody mapping, resource monitoring, self-regulation, speaker tempo, and all core features.
- Additive polish phase:
    - Micro-breath sound logic (audio/breath.py)
    - Thought leakage token generator (audio/thought_leakage.py)
    - Idle face drift (audio/idle_face_drift.py)
    - Blink assist (audio/blink_assist.py)
    - Audio stall guard (audio/audio_stall_guard.py)
    - OSC backpressure guard (audio/osc_backpressure_guard.py)
    - All polish features are off by default and fully fail-soft
    - Determinism and gating tests for polish features
- No refactors, no behavior changes, no new states
- All tests remain passing
