import argparse
import random
from pprint import pprint
import sys
from pathlib import Path

# Ensure the repository root (parent of the package dir) is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from neuro_vrchat_ai.core.speech_brain import make_speech_plan
except Exception:
    # fallback when package import isn't available (run as script)
    from core.speech_brain import make_speech_plan

CASES = [
    ("calm_high_conf",     dict(glitch=0.05, confidence=0.85, curiosity=0.25, social_pressure=0.25, arousal=0.30, valence=0.20)),
    ("curious_mid_conf",   dict(glitch=0.20, confidence=0.60, curiosity=0.80, social_pressure=0.35, arousal=0.45, valence=0.10)),
    ("pressured_mid_conf", dict(glitch=0.15, confidence=0.60, curiosity=0.30, social_pressure=0.90, arousal=0.55, valence=0.05)),
    ("glitchy_low_conf",   dict(glitch=0.75, confidence=0.35, curiosity=0.55, social_pressure=0.60, arousal=0.65, valence=-0.05)),
    ("nervous_low_conf",   dict(glitch=0.35, confidence=0.30, curiosity=0.40, social_pressure=0.85, arousal=0.70, valence=-0.20)),
    ("happy_talky",        dict(glitch=0.10, confidence=0.75, curiosity=0.50, social_pressure=0.40, arousal=0.60, valence=0.60)),
]

TEXTS = [
    "今日なにしてた？",
    "それって結局どういうこと？",
]


def fmt_osc(osc):
    if not isinstance(osc, dict):
        return ""
    keys = ["N_Arousal", "N_Valence", "N_Gesture", "N_Look", "N_State"]
    parts = []
    for k in keys:
        if k in osc:
            parts.append(f"{k}={osc[k]}")
    return " | osc: {" + ", ".join(parts) + "}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=123)
    ap.add_argument("--cases", type=int, default=0, help="Number of cases to print (0=all)")
    args = ap.parse_args()

    # seed global random for any code paths that use it
    random.seed(args.seed)

    use_cases = CASES[:args.cases] if args.cases and args.cases > 0 else CASES

    for case_name, s in use_cases:
        print("=" * 90)
        print(f"CASE: {case_name}  scalars={s}")
        for text in TEXTS:
            print("-" * 90)
            print(f"INPUT: {text}")
            plan = make_speech_plan(
                reply=text,
                glitch=s["glitch"],
                curiosity=s["curiosity"],
                confidence=s["confidence"],
                social_pressure=s["social_pressure"],
                arousal=s["arousal"],
                valence=s["valence"],
                seed=args.seed,
            )
            sp = plan.get("speech_plan") or []
            for c in sp:
                cid = c.get("id", "?")
                ctype = c.get("type", "?")
                pause = c.get("pause_ms", 0)
                t = (c.get("text") or "").replace("\n", "\\n")
                print(f"[{cid}] ({ctype}) pause={pause:>3}ms: {t}{fmt_osc(c.get('osc'))}")


if __name__ == "__main__":
    main()