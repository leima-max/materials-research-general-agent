#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.request import urlopen

SKILL_DIR = Path(__file__).resolve().parents[1]
VENDOR_DIR = SKILL_DIR / "vendor" / "site-packages"
PACKAGE_DIR = VENDOR_DIR / "pyradi"
RAW_BASE = "https://raw.githubusercontent.com/NelisW/pyradi/master/pyradi"
DEFAULT_MODULES = ["rydetector.py"]
DEFAULT_PIP_DEPS = ["numpy", "scipy", "matplotlib"]


def _pythonpath_with_vendor() -> str:
    existing = os.environ.get("PYTHONPATH", "")
    parts = [str(VENDOR_DIR)]
    if existing:
        parts.append(existing)
    return os.pathsep.join(parts)


def _run(command: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True, check=False, env=env)


def _install_deps(deps: list[str], upgrade: bool) -> subprocess.CompletedProcess:
    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        *deps,
        "--target",
        str(VENDOR_DIR),
        "--disable-pip-version-check",
        "--no-warn-script-location",
    ]
    if upgrade:
        command.append("--upgrade")
    return _run(command)


def _download_module(module_name: str) -> Path:
    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)
    target = PACKAGE_DIR / module_name
    url = f"{RAW_BASE}/{module_name}"
    content = urlopen(url, timeout=60).read().decode("utf-8")
    target.write_text(content, encoding="utf-8")
    return target


def _write_init(modules: list[str]) -> None:
    exports = [Path(m).stem for m in modules]
    lines = ["# Auto-generated pyradi subset for OpenClaw skill use", f"__all__ = {exports!r}", ""]
    (PACKAGE_DIR / "__init__.py").write_text("\n".join(lines), encoding="utf-8")


def _verify_import() -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = _pythonpath_with_vendor()
    return _run(
        [
            sys.executable,
            "-c",
            "import pyradi.rydetector as ryd; print(ryd.__file__); print(sorted(ryd.__all__))",
        ],
        env=env,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Install a workspace-local pyradi detector subset")
    parser.add_argument("--modules", nargs="*", default=DEFAULT_MODULES, help="Raw pyradi modules to vendor, e.g. rydetector.py")
    parser.add_argument("--upgrade", action="store_true", help="Upgrade dependencies before download")
    args = parser.parse_args()

    VENDOR_DIR.mkdir(parents=True, exist_ok=True)
    dep_proc = _install_deps(DEFAULT_PIP_DEPS, upgrade=args.upgrade)

    downloaded: list[str] = []
    download_errors: dict[str, str] = {}
    for module_name in args.modules:
        try:
            downloaded.append(str(_download_module(module_name)))
        except Exception as exc:  # pragma: no cover - network dependent
            download_errors[module_name] = str(exc)

    if downloaded:
        _write_init(args.modules)

    verify_proc = _verify_import() if not download_errors else subprocess.CompletedProcess([], 1, "", json.dumps(download_errors))

    status = "ok" if dep_proc.returncode == 0 and verify_proc.returncode == 0 and not download_errors else "error"
    result = {
        "status": status,
        "summary": "Installed pyradi detector subset into workspace-local vendor directory." if status == "ok" else "Failed to install or verify pyradi detector subset.",
        "results": {
            "vendor_dir": str(VENDOR_DIR),
            "downloaded_modules": downloaded,
            "dependency_returncode": dep_proc.returncode,
            "verify_returncode": verify_proc.returncode,
        },
    }
    if download_errors:
        result["results"]["download_errors"] = download_errors
    if dep_proc.stdout.strip():
        result["results"]["dependency_stdout"] = dep_proc.stdout.strip()
    if dep_proc.stderr.strip():
        result["results"]["dependency_stderr"] = dep_proc.stderr.strip()
    if verify_proc.stdout.strip():
        result["results"]["verify_stdout"] = verify_proc.stdout.strip()
    if verify_proc.stderr.strip():
        result["results"]["verify_stderr"] = verify_proc.stderr.strip()

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
