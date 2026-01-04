#!/usr/bin/env py -3.11
"""Top-level runner for the speech_plan sample printer.

This wrapper prefers importing the package-level script (pattern A). If import fails
or the module has no `main`, it falls back to executing the script file directly
(pattern B) so it works in diverse environments.

Usage:
  py -3.11 -u print_speech_plan_samples.py --seed 123
"""
import runpy
from pathlib import Path

try:
    # Pattern A: prefer direct import if package is present
    from neuro_vrchat_ai.scripts.print_speech_plan_samples import main  # type: ignore
except Exception:
    # Fallback (Pattern B): execute the script file directly
    here = Path(__file__).resolve().parent
    script = here / "scripts" / "print_speech_plan_samples.py"

    def main():
        runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()
