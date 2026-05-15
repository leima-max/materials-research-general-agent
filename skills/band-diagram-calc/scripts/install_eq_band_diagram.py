#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
VENDOR_DIR = SKILL_DIR / "vendor" / "site-packages"
DEFAULT_VERSION = "0.1.0"


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
    env.setdefault("MPLBACKEND", "Agg")
    return _run([
        sys.executable,
        "-c",
        "import eq_band_diagram as m; print(getattr(m, '__file__', 'unknown')); print(hasattr(m, 'calc_layer_stack')); print(m.Si.name, m.GaAs.name)",
    ], env=env)


def main() -> None:
    parser = argparse.ArgumentParser(description="Install eq_band_diagram into the current workspace skill vendor directory")
    parser.add_argument("--version", default=DEFAULT_VERSION, help="eq_band_diagram version to install")
    parser.add_argument("--upgrade", action="store_true", help="Upgrade/reinstall the selected version")
    args = parser.parse_args()

    VENDOR_DIR.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        f"eq_band_diagram=={args.version}",
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
        "summary": "Installed eq_band_diagram into workspace-local vendor directory." if status == "ok" else "Failed to install or verify eq_band_diagram.",
        "assumptions": [
            "Installation target is workspace-local and does not modify global PATH.",
            "solve_band_diagram.py will prefer the local vendor install when needed.",
        ],
        "results": {
            "vendor_dir": str(VENDOR_DIR),
            "install_command": command,
            "install_returncode": install_proc.returncode,
            "verify_returncode": verify_proc.returncode,
        },
        "artifacts": [],
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
