#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
VENDOR_DIR = SKILL_DIR / "vendor" / "site-packages"
DEFAULT_SPEC = "pyFAI"


def _pythonpath_with_vendor() -> str:
    existing = os.environ.get("PYTHONPATH", "")
    parts = [str(VENDOR_DIR)]
    if existing:
        parts.append(existing)
    return os.pathsep.join(parts)


def _run(command: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True, check=False, env=env)


def _verify_import() -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = _pythonpath_with_vendor()
    return _run(
        [
            sys.executable,
            "-c",
            "import pyFAI, fabio, numpy; print(pyFAI.__version__); print(pyFAI.__file__)",
        ],
        env=env,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Install pyFAI into this skill's workspace-local vendor directory")
    parser.add_argument("--spec", default=DEFAULT_SPEC, help="pip spec to install, default: pyFAI")
    parser.add_argument("--upgrade", action="store_true", help="upgrade/reinstall the selected spec")
    args = parser.parse_args()

    VENDOR_DIR.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        args.spec,
        "--target",
        str(VENDOR_DIR),
        "--disable-pip-version-check",
        "--no-warn-script-location",
    ]
    if args.upgrade:
        command.append("--upgrade")

    install_proc = _run(command)
    verify_proc = _verify_import()

    status = "ok" if install_proc.returncode == 0 and verify_proc.returncode == 0 else "error"
    result = {
        "status": status,
        "summary": "Installed pyFAI into workspace-local vendor directory." if status == "ok" else "Failed to install or verify pyFAI.",
        "results": {
            "vendor_dir": str(VENDOR_DIR),
            "install_command": command,
            "install_returncode": install_proc.returncode,
            "verify_returncode": verify_proc.returncode,
        },
    }
    if install_proc.stdout.strip():
        result["results"]["install_stdout"] = install_proc.stdout.strip()
    if install_proc.stderr.strip():
        result["results"]["install_stderr"] = install_proc.stderr.strip()
    if verify_proc.stdout.strip():
        result["results"]["verify_stdout"] = verify_proc.stdout.strip()
    if verify_proc.stderr.strip():
        result["results"]["verify_stderr"] = verify_proc.stderr.strip()

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
