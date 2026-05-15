#!/usr/bin/env python3
"""Install PyThesisPlot dependencies into the skill-local vendor directory."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
REQUIREMENTS = SKILL_DIR / "requirements.txt"
TARGET = SKILL_DIR / "vendor" / "site-packages"


def main() -> int:
    parser = argparse.ArgumentParser(description="Install PyThesisPlot dependencies locally.")
    parser.add_argument("--upgrade", action="store_true", help="Pass --upgrade to pip.")
    args = parser.parse_args()

    if not REQUIREMENTS.exists():
        raise SystemExit(f"requirements.txt not found: {REQUIREMENTS}")

    TARGET.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--target",
        str(TARGET),
        "-r",
        str(REQUIREMENTS),
    ]
    if args.upgrade:
        cmd.insert(4, "--upgrade")

    print("Installing PyThesisPlot dependencies into:")
    print(f"  {TARGET}")
    completed = subprocess.run(cmd)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
