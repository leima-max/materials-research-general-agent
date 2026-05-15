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
    steps.append(run([PY, "scripts/integrate_xrd.py", "--config", "assets/demo/demo_config_1d.json"]))
    steps.append(run([PY, "scripts/integrate_xrd.py", "--config", "assets/demo/demo_config_2d.json"]))
    steps.append(run([PY, "scripts/integrate_xrd.py", "--config", "assets/demo/demo_config_azimuthal.json"]))

    path_1d = SKILL_DIR / "assets" / "demo" / "outputs_1d" / "synthetic_texture_summary.json"
    path_2d = SKILL_DIR / "assets" / "demo" / "outputs_2d" / "synthetic_texture_summary.json"
    path_az = SKILL_DIR / "assets" / "demo" / "outputs_azimuthal" / "synthetic_texture_summary.json"

    ok = all(step["returncode"] == 0 for step in steps)

    if path_1d.exists():
        data = load_json(path_1d)
        checks.append({
            "name": "1d_peaks_present",
            "pass": bool(data.get("peaks")),
            "value": len(data.get("peaks") or []),
        })
    else:
        checks.append({"name": "1d_summary_exists", "pass": False, "value": None})

    if path_2d.exists():
        data = load_json(path_2d)
        checks.append({
            "name": "2d_shape_present",
            "pass": data.get("shape") is not None,
            "value": data.get("shape"),
        })
    else:
        checks.append({"name": "2d_summary_exists", "pass": False, "value": None})

    if path_az.exists():
        data = load_json(path_az)
        stats = data.get("profile_stats") or {}
        checks.append({
            "name": "azimuthal_fwhm_present",
            "pass": stats.get("fwhm") is not None,
            "value": stats.get("fwhm"),
        })
        checks.append({
            "name": "azimuthal_window_present",
            "pass": data.get("profile_radial_range") is not None,
            "value": data.get("profile_radial_range"),
        })
    else:
        checks.append({"name": "azimuthal_summary_exists", "pass": False, "value": None})

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
