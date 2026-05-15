#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parents[1]
VENDOR_DIR = SKILL_DIR / "vendor" / "site-packages"
DEFAULT_VERSION = "2024.3.24"
OPTIONAL_EXTRAS = {
    "ase": ["ase>=3.23"],
    "alignn": ["ase>=3.23", "alignn"],
    "matgl": ["ase>=3.23", "matgl"],
}


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
    return _run([
        sys.executable,
        "-c",
        "import intermat, pkgutil; print(getattr(intermat, '__file__', 'unknown')); print(sorted(m.name for m in pkgutil.iter_modules(intermat.__path__))[:20])",
    ], env=env)


def _verify_optional_imports(extras: list[str]) -> dict[str, subprocess.CompletedProcess]:
    env = os.environ.copy()
    env["PYTHONPATH"] = _pythonpath_with_vendor()
    checks: dict[str, subprocess.CompletedProcess] = {}
    for extra in extras:
        module_name = "ase" if extra == "ase" else extra
        checks[extra] = _run([
            sys.executable,
            "-c",
            f"import {module_name}; print(getattr({module_name}, '__file__', 'unknown'))",
        ], env=env)
    return checks


def _parse_extras(raw: list[str]) -> list[str]:
    items: list[str] = []
    for value in raw:
        for part in value.split(","):
            item = part.strip().lower()
            if item:
                items.append(item)
    unknown = sorted({item for item in items if item not in OPTIONAL_EXTRAS})
    if unknown:
        raise ValueError(
            f"Unknown extras: {', '.join(unknown)}. Allowed extras: {', '.join(sorted(OPTIONAL_EXTRAS))}"
        )
    ordered: list[str] = []
    for item in items:
        if item not in ordered:
            ordered.append(item)
    return ordered


def _build_extra_packages(extras: list[str]) -> list[str]:
    packages: list[str] = []
    for extra in extras:
        for pkg in OPTIONAL_EXTRAS[extra]:
            if pkg not in packages:
                packages.append(pkg)
    return packages


def main() -> None:
    parser = argparse.ArgumentParser(description="Install intermat into the current workspace skill vendor directory")
    parser.add_argument("--version", default=DEFAULT_VERSION, help="intermat version to install")
    parser.add_argument("--upgrade", action="store_true", help="Upgrade/reinstall the selected version")
    parser.add_argument(
        "--extras",
        action="append",
        default=[],
        help="Optional calculator extras to install into the same vendor dir. Allowed: ase, alignn, matgl. Can be repeated or comma-separated.",
    )
    args = parser.parse_args()

    extras = _parse_extras(args.extras)
    extra_packages = _build_extra_packages(extras)

    VENDOR_DIR.mkdir(parents=True, exist_ok=True)

    core_command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        f"intermat=={args.version}",
        "--target",
        str(VENDOR_DIR),
        "--disable-pip-version-check",
        "--no-warn-script-location",
    ]
    if args.upgrade:
        core_command.append("--upgrade")

    install_proc = _run(core_command)
    extra_installs: dict[str, dict[str, Any]] = {}
    for extra in extras:
        packages = OPTIONAL_EXTRAS[extra]
        extra_command = [
            sys.executable,
            "-m",
            "pip",
            "install",
            *packages,
            "--target",
            str(VENDOR_DIR),
            "--disable-pip-version-check",
            "--no-warn-script-location",
        ]
        if args.upgrade:
            extra_command.append("--upgrade")
        proc = _run(extra_command)
        extra_installs[extra] = {
            "packages": packages,
            "command": extra_command,
            "returncode": proc.returncode,
        }
        if proc.stdout.strip():
            extra_installs[extra]["stdout"] = proc.stdout.strip()
        if proc.stderr.strip():
            extra_installs[extra]["stderr"] = proc.stderr.strip()

    verify_proc = _verify_import()
    optional_verify = _verify_optional_imports(extras)

    optional_ok = all(proc.returncode == 0 for proc in optional_verify.values())
    extra_install_ok = all(item["returncode"] == 0 for item in extra_installs.values())
    status = "ok" if install_proc.returncode == 0 and verify_proc.returncode == 0 and extra_install_ok and optional_ok else "error"
    result = {
        "status": status,
        "summary": "Installed intermat into workspace-local vendor directory." if status == "ok" else "Failed to install or verify intermat.",
        "assumptions": [
            "Installation target is workspace-local and does not modify global PATH.",
            "run_band_offset_analysis.py will prefer the local vendor install when needed.",
        ],
        "results": {
            "vendor_dir": str(VENDOR_DIR),
            "install_command": core_command,
            "install_returncode": install_proc.returncode,
            "verify_returncode": verify_proc.returncode,
            "requested_extras": extras,
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
    if extra_packages:
        result["results"]["extra_packages"] = extra_packages
        result["results"]["extra_install_results"] = extra_installs
        result["results"]["extra_verify"] = {
            extra: {
                "returncode": proc.returncode,
                **({"stdout": proc.stdout.strip()} if proc.stdout.strip() else {}),
                **({"stderr": proc.stderr.strip()} if proc.stderr.strip() else {}),
            }
            for extra, proc in optional_verify.items()
        }
        result["assumptions"].append(
            "Optional extras are installed into the same workspace-local vendor directory for calculator routes that need additional Python packages."
        )

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
