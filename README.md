# Example config flags for presence polish (all default false/safe):
- enable_idle_face_drift: false
- enable_blink_hint: false
- idle_face_drift_amp: 0.04   # hard clamp <= 0.05
- idle_face_drift_period_sec: 50.0  # hard clamp >= 40
- idle_face_drift_tick_hz: 0.2  # 1 update / 5s
- blink_min_sec: 3.0
- blink_max_sec: 8.0
- blink_pulse_ms: 120  # send 1 then 0 after pulse duration
- osc_latency_downgrade_ms: 35
- osc_latency_recover_ms: 20
- osc_face_update_hz_danger: 0.05  # degrade to 1/20s
- presence_seed: 1337
# Philosophy: Why Silence Matters
Silence is a core part of believable social AI. It allows for natural pacing, avoids overwhelming users, and supports subtle emotional presence. The system is designed to speak only when necessary, using silence and micro-expressions to convey intelligence and presence.

# Timing Intelligence
All timing, delays, and expressive behaviors are deterministic and context-aware. The system adapts to user tempo, system load, and emotional state, ensuring responses feel natural and never rushed or spammy.

# Why No VRChat API
The system uses only OSC for avatar control, avoiding any VRChat internal API. This ensures maximum compatibility, privacy, and future-proofing, and avoids any risk of breaking changes or privacy violations.

# Fail-soft Doctrine
Every subsystem is designed to fail softly. If a feature cannot run (e.g., audio device missing, resource probe fails), the system silently degrades to safe defaults, never crashing or spamming errors.

# Determinism & Testing
All expressive and timing logic is deterministic and testable. Randomness is always seeded or derived from context, and all features are covered by unit tests for determinism, gating, and cooldowns. No snapshot or device-dependent tests are used.
# neuro_vrchat_ai

## Speech Plan Debug / Tuning

VRChatを起動せずに、Neuro風の `speech_plan`（`think`/`aside`/`self_correct`/`pause` など）を
スカラー組合せごとに確認できます。seed固定で再現性があります。

### Run

```bash
py -3.11 -u print_speech_plan_samples.py
```

### Speech Plan Debug / Tuning

Reproducible:

```bash
py -3.11 -u print_speech_plan_samples.py --seed 123 --cases 6
```

※ このスクリプトは表示専用で、本体の挙動は変更しません。

### Smoke tests (agents)

There are two lightweight, deterministic smoke entry points (network-free):

- **Direct flag**: `run_demo_smoke(agents_enabled=True)` — verifies runtime wiring programmatically.
- **Config-driven**: `resolve_agents_enabled_from_config(cfg)` → `run_demo_smoke(...)` — verifies the real config path (`agents.enabled: true`).

Both are covered by CI via `tests/test_demo_agents_smoke.py`.
