#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
PY = sys.executable


def run(cmd: list[str]) -> dict:
    proc = subprocess.run(cmd, cwd=SKILL_DIR, capture_output=True, text=True)
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    steps = []
    checks = []

    steps.append(run([PY, "scripts/generate_demo_dataset.py"]))
    steps.append(run([PY, "scripts/compute_detector_metrics.py", "--config", "assets/demo/demo_config_measured_noise.json"]))
    steps.append(run([PY, "scripts/compute_detector_metrics.py", "--config", "assets/demo/demo_config_shot_noise.json"]))

    measured_summary = SKILL_DIR / "assets" / "demo" / "outputs_measured_noise" / "device_a_measured_noise_summary.json"
    shot_summary = SKILL_DIR / "assets" / "demo" / "outputs_shot_noise" / "device_a_shot_noise_summary.json"

    ok = all(step["returncode"] == 0 for step in steps)

    if measured_summary.exists():
        data = load_json(measured_summary)
        checks.append({
            "name": "measured_noise_mode",
            "pass": data.get("noise_mode") == "measured_density_to_rms",
            "value": data.get("noise_mode"),
        })
        checks.append({
            "name": "measured_qe_mode",
            "pass": data.get("qe_input_mode") == "percent",
            "value": data.get("qe_input_mode"),
        })
    else:
        checks.append({"name": "measured_summary_exists", "pass": False, "value": None})

    if shot_summary.exists():
        data = load_json(shot_summary)
        checks.append({
            "name": "shot_noise_mode",
            "pass": data.get("noise_mode") == "shot_noise_from_dark_current",
            "value": data.get("noise_mode"),
        })
        dstar = (data.get("peaks") or {}).get("dstar") or {}
        checks.append({
            "name": "shot_dstar_present",
            "pass": dstar.get("value") is not None,
            "value": dstar.get("value"),
        })
    else:
        checks.append({"name": "shot_summary_exists", "pass": False, "value": None})

    ok = ok and all(c["pass"] for c in checks)
    result = {
        "status": "ok" if ok else "error",
        "steps": steps,
        "checks": checks,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
