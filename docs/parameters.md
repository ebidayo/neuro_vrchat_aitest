# Shinano parameter mapping (required by Phase1 / v1.2)

All parameters must be numeric (int/float/bool) and sent under `/avatar/parameters/<name>`.
Strings must be sent only via `/chatbox/input` as `[text, sendImmediately, notify]`.

Mapping used by this project:

- Emotion (int)        # state id mapping: IDLE=0 GREET=1 TALK=2 REACT=3 FOCUS=4 ALERT=5 SEARCH=6 ERROR=7 RECOVER=8
- Face (int)           # facial preset index
- LookX (float)        # -1..1
- LookY (float)        # -1..1
- TalkSpeed (float)    # 0..1 (speech speed proxy)
- Mood (float)         # -1..1
- Blink (float)        # 0..1

Verification steps:
1. Run `python main.py --demo` and watch log outputs.
2. Observe a VRChat instance using Shinano avatar connected to 127.0.0.1:9000; ensure parameters update and avatar reacts.
3. Use network capture / osc monitoring tools to validate messages go to `/avatar/parameters/<name>` and only numbers are sent.
4. For chatbox output, verify `/chatbox/input` is sent as a 3-arg list: [text, True, True].

Notes:
- OSC messages are rate-limited to 10Hz and only diffs are transmitted.
- If you need to tune Face indices for specific Shinano expressions, edit `main.py` face_presets mapping.
