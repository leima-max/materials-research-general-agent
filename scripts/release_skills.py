#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "skills"
DIST_DIR = ROOT / "dist" / "skills"
SKILL_CREATOR_SCRIPTS = Path(os.environ.get(
    "SKILL_CREATOR_SCRIPTS",
    str(ROOT / "tools" / "skill-creator" / "scripts"),
))
QUICK_VALIDATE = SKILL_CREATOR_SCRIPTS / "quick_validate.py"
PACKAGE_SKILL = SKILL_CREATOR_SCRIPTS / "package_skill.py"
DEFAULT_SKILLS = ["photodetector-pyradi", "xrd-pyfai"]
PY = sys.executable


def run(cmd: list[str], cwd: Path | None = None, extra_env: dict[str, str] | None = None) -> dict:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    return {
        "cmd": cmd,
        "cwd": str(cwd) if cwd else None,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def clean_demo_outputs(skill_dir: Path) -> list[str]:
    removed: list[str] = []
    demo_dir = skill_dir / "assets" / "demo"
    if not demo_dir.exists():
        return removed
    for path in sorted(demo_dir.glob("outputs_*")):
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
            removed.append(str(path))
    return removed


def package_size_mb(path: Path) -> float | None:
    return round(path.stat().st_size / 1024 / 1024, 2) if path.exists() else None


def release_skill(skill_name: str) -> dict:
    skill_dir = SKILLS_DIR / skill_name
    scripts_dir = skill_dir / "scripts"
    result: dict[str, object] = {
        "skill": skill_name,
        "skill_dir": str(skill_dir),
        "steps": [],
        "cleanup": {},
        "artifacts": {},
        "status": "error",
    }

    if not skill_dir.exists():
        result["error"] = f"skill not found: {skill_dir}"
        return result

    smoke_script = scripts_dir / "run_smoke_test.py"
    prune_script = scripts_dir / "prune_vendor.py"

    result["cleanup"] = {"pre_package_removed_demo_outputs": clean_demo_outputs(skill_dir)}

    validate_before = run([PY, str(QUICK_VALIDATE), str(skill_dir)], cwd=ROOT)
    result["steps"].append({"name": "validate_before", **validate_before})
    if validate_before["returncode"] != 0:
        result["error"] = "validate_before failed"
        return result

    if prune_script.exists():
        prune = run([PY, str(prune_script)], cwd=ROOT)
        result["steps"].append({"name": "prune_vendor", **prune})
        if prune["returncode"] != 0:
            result["error"] = "prune_vendor failed"
            return result

    if smoke_script.exists():
        smoke = run([PY, str(smoke_script)], cwd=ROOT)
        result["steps"].append({"name": "smoke_test", **smoke})
        if smoke["returncode"] != 0:
            result["error"] = "smoke_test failed"
            return result
    else:
        result["steps"].append({"name": "smoke_test", "skipped": True, "reason": "script not found"})

    result["cleanup"] = {
        **result["cleanup"],
        "post_smoke_removed_demo_outputs": clean_demo_outputs(skill_dir),
    }

    if prune_script.exists():
        prune_after_smoke = run([PY, str(prune_script)], cwd=ROOT)
        result["steps"].append({"name": "prune_after_smoke", **prune_after_smoke})
        if prune_after_smoke["returncode"] != 0:
            result["error"] = "prune_after_smoke failed"
            return result

    validate_after = run([PY, str(QUICK_VALIDATE), str(skill_dir)], cwd=ROOT)
    result["steps"].append({"name": "validate_after", **validate_after})
    if validate_after["returncode"] != 0:
        result["error"] = "validate_after failed"
        return result

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    package_path = DIST_DIR / f"{skill_name}.skill"
    if package_path.exists():
        package_path.unlink()

    package = run(
        [PY, str(PACKAGE_SKILL), str(skill_dir), str(DIST_DIR)],
        cwd=ROOT,
        extra_env={"PYTHONIOENCODING": "utf-8"},
    )
    result["steps"].append({"name": "package", **package})
    if package["returncode"] != 0:
        result["error"] = "package failed"
        return result

    result["artifacts"] = {
        "package": str(package_path),
        "package_size_mb": package_size_mb(package_path),
    }
    result["status"] = "ok"
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="One-click release flow for workspace skills")
    parser.add_argument("skills", nargs="*", help="Skill names to release. Defaults to photodetector-pyradi and xrd-pyfai")
    parser.add_argument("--report", default=str(DIST_DIR / "release-report.json"), help="Path to JSON report")
    args = parser.parse_args()

    skills = args.skills or DEFAULT_SKILLS
    report = {
        "status": "ok",
        "root": str(ROOT),
        "skills": [],
    }

    for skill_name in skills:
        item = release_skill(skill_name)
        report["skills"].append(item)
        if item.get("status") != "ok":
            report["status"] = "error"

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=True))
    sys.exit(0 if report["status"] == "ok" else 1)


if __name__ == "__main__":
    main()
