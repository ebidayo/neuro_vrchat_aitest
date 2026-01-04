
# neuro_vrchat_ai

## What this is
A deterministic, event-driven autonomous presence system for VRChat avatars. It models silence, subtlety, and emotional nuance, using only OSC for avatar control. The system is designed to feel alive without constant speech, prioritizing believable presence and privacy.

## Core Philosophy
Silence is a feature, not a bug. Fewer words and longer pauses make an agent feel more intelligent and less intrusive. "Doing nothing" is a deliberate action, allowing the system to yield space and avoid overwhelming users. Determinism ensures every behavior is reproducible, testable, and free from hidden randomness, supporting both reliability and trust.

## What this is NOT
- Not a chatbot
- Not a VRChat bot using internal APIs
- Not an LLM wrapper
- Not self-modifying or self-training

## Architecture Overview
- Event-driven StateMachine
- Sacred chunk boundaries for speech and actions
- Planner → Critic → Finalizer (mock LLM)
- Scalar-based emotion model (valence, interest, arousal)
- Fail-soft subsystems for all expressive and safety features

## Presence Without Speech
The system maintains presence even in silence. During IDLE, it uses subtle face drift and micro-expressions. Starters and emotional afterglow provide gentle cues of aliveness. Micro-expressions and rare, meaningful actions are favored over frequent speech, making the agent feel present but never overwhelming.


## Safety & Stability
All subsystems are designed to fail softly: if a feature cannot run, it degrades silently to safe defaults. ResourceWatcher and SelfRegulator monitor system health, with ALERT states taking priority over all else. Silence is always safer than apology spam or error loops.

**Emergency JP Chat Behavior:**
- If the message content changes, it is sent immediately regardless of cooldown.
- Disaster-level chat uses a fixed short template.

## Determinism & Testing
Determinism is enforced throughout: all timing and expressive logic use a TimeProvider and seeded RNG. Tests are written with pytest, require no network, and cover all core and polish features. The system is built with a CI mindset for reliability and reproducibility.

## Requirements
- Python 3.11
- VRChat (OSC enabled)
- Local TTS (optional)

## Running the System
```
pip install -r requirements.txt
python main.py
```

## License
See LICENSE file.
