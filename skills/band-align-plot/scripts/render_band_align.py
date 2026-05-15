#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from build_config import (
    infer_alignment_type,
    load_payload,
    payload_to_bapt_config,
    validate_payload,
    write_bapt_config,
)

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
LOCAL_VENDOR_DIR = SKILL_DIR / "vendor" / "site-packages"


def _default_output_name(payload: dict) -> str:
    title = payload.get("inputs", {}).get("title")
    if title:
        safe = "".join(ch if ch.isalnum() else "_" for ch in title).strip("_")
        if safe:
            return f"{safe}.pdf"
    return "alignment.pdf"



def _write_command_preview(command: list[str], output_dir: Path) -> Path:
    preview_path = output_dir / "bapt_command.txt"
    preview_path.write_text(" ".join(shlex.quote(part) for part in command), encoding="utf-8")
    return preview_path



def _run_bapt(command: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True, check=False, env=env)



def _local_bapt_available() -> bool:
    return (LOCAL_VENDOR_DIR / "bapt").exists()



def _env_with_local_vendor() -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(
        [str(LOCAL_VENDOR_DIR)] + ([existing] if existing else [])
    )
    return env



def _resolve_bapt_backend() -> tuple[list[str] | None, dict[str, str] | None, str]:
    bapt_exe = shutil.which("bapt")
    if bapt_exe:
        return [bapt_exe], None, "path"

    if _local_bapt_available():
        return [sys.executable, "-m", "bapt.cli"], _env_with_local_vendor(), "local_vendor"

    return None, None, "missing"



def main() -> None:
    parser = argparse.ArgumentParser(description="Render static band alignment plots via bapt")
    parser.add_argument("--input", required=True, help="Path to band-align-plot JSON input")
    parser.add_argument("--output-dir", required=True, help="Directory for generated files")
    parser.add_argument(
        "--output-file",
        default=None,
        help="Output figure filename (defaults to title-derived name or alignment.pdf)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate bapt config and command preview without invoking bapt",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        payload = load_payload(args.input)
        validate_payload(payload)

        config = payload_to_bapt_config(payload)
        config_path = write_bapt_config(config, output_dir / "bapt_config.yaml")

        output_name = args.output_file or _default_output_name(payload)
        output_path = output_dir / output_name

        backend_cmd, backend_env, backend_source = _resolve_bapt_backend()
        command = [*(backend_cmd or ["bapt"]), "-f", str(config_path), "-o", str(output_path)]
        command_preview = _write_command_preview(command, output_dir)

        assumptions = []
        artifacts = [
            {"type": "config", "path": str(config_path)},
            {"type": "command_preview", "path": str(command_preview)},
        ]
        results = {
            "backend": "bapt",
            "backend_source": backend_source,
            "alignment_type": infer_alignment_type(payload),
            "config_mode": payload.get("mode"),
            "materials_used": [m["name"] for m in payload.get("inputs", {}).get("materials", [])],
            "executed": False,
        }

        if args.dry_run:
            assumptions.append("Dry-run mode: bapt was not invoked.")
            result = {
                "status": "ok",
                "summary": "Generated bapt config and command preview.",
                "assumptions": assumptions,
                "results": results,
                "artifacts": artifacts,
            }
        elif backend_cmd is None:
            assumptions.append("bapt was not found in PATH or in the workspace-local vendor directory.")
            assumptions.append("Run scripts/install_bapt.py to enable local rendering without global installation.")
            result = {
                "status": "warning",
                "summary": "Generated bapt config, but bapt is not installed in this environment.",
                "assumptions": assumptions,
                "results": results,
                "artifacts": artifacts,
            }
        else:
            if backend_source == "local_vendor":
                assumptions.append("Using workspace-local bapt installation from skills/band-align-plot/vendor/site-packages.")
            proc = _run_bapt(command, env=backend_env)
            results["executed"] = True
            results["returncode"] = proc.returncode
            if proc.stdout.strip():
                results["stdout"] = proc.stdout.strip()
            if proc.stderr.strip():
                results["stderr"] = proc.stderr.strip()

            if proc.returncode != 0:
                result = {
                    "status": "error",
                    "summary": "bapt execution failed.",
                    "assumptions": assumptions,
                    "results": results,
                    "artifacts": artifacts,
                }
            else:
                if output_path.exists():
                    artifacts.append({"type": "figure", "path": str(output_path)})
                result = {
                    "status": "ok",
                    "summary": "Rendered band alignment figure through bapt.",
                    "assumptions": assumptions,
                    "results": results,
                    "artifacts": artifacts,
                }

    except Exception as exc:
        result = {
            "status": "error",
            "summary": "Failed to prepare or render the bapt job.",
            "assumptions": [],
            "results": {},
            "artifacts": [],
            "error": str(exc),
        }

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
