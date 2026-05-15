#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
VENDOR_DIR = SKILL_DIR / "vendor" / "site-packages"

REMOVE_FILE_SUFFIXES = {".pyc", ".pyo", ".a", ".pxd", ".pyi"}
REMOVE_DIR_NAMES = {"__pycache__", "examples", "example", "tests", "test"}
KEEP_EXACT_FILES = {
    "numpy/_core/tests/__init__.py",
    "numpy/_core/tests/_natype.py",
}


def _safe_unlink(path: Path) -> int:
    size = path.stat().st_size if path.exists() and path.is_file() else 0
    path.unlink(missing_ok=True)
    return size


def _safe_rmtree(path: Path) -> int:
    total = 0
    if path.exists():
        for f in path.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
        shutil.rmtree(path, ignore_errors=True)
    return total


def main() -> None:
    removed_files = 0
    removed_dirs = 0
    bytes_removed = 0

    if not VENDOR_DIR.exists():
        print(json.dumps({"status": "error", "reason": f"missing vendor dir: {VENDOR_DIR}"}, indent=2))
        return

    for path in sorted(VENDOR_DIR.rglob("*"), key=lambda p: (len(p.parts), str(p)), reverse=True):
        if not path.exists():
            continue
        rel = path.relative_to(VENDOR_DIR).as_posix()

        if path.is_file() and path.suffix.lower() in REMOVE_FILE_SUFFIXES:
            bytes_removed += _safe_unlink(path)
            removed_files += 1
            continue

        if path.is_dir() and path.name in REMOVE_DIR_NAMES:
            if rel == "numpy/_core/tests":
                for child in list(path.rglob("*")):
                    if child.is_file():
                        child_rel = child.relative_to(VENDOR_DIR).as_posix()
                        if child_rel not in KEEP_EXACT_FILES:
                            bytes_removed += _safe_unlink(child)
                            removed_files += 1
                    elif child.is_dir() and child.name == "__pycache__":
                        bytes_removed += _safe_rmtree(child)
                        removed_dirs += 1
                for child in sorted(path.iterdir(), reverse=True):
                    child_rel = child.relative_to(VENDOR_DIR).as_posix()
                    if child.is_dir():
                        bytes_removed += _safe_rmtree(child)
                        removed_dirs += 1
                    elif child_rel not in KEEP_EXACT_FILES:
                        bytes_removed += _safe_unlink(child)
                        removed_files += 1
            else:
                bytes_removed += _safe_rmtree(path)
                removed_dirs += 1

    for path in sorted(VENDOR_DIR.rglob("bin"), reverse=True):
        if path.is_dir():
            bytes_removed += _safe_rmtree(path)
            removed_dirs += 1

    result = {
        "status": "ok",
        "vendor_dir": str(VENDOR_DIR),
        "removed_files": removed_files,
        "removed_dirs": removed_dirs,
        "bytes_removed": bytes_removed,
        "mb_removed": round(bytes_removed / 1024 / 1024, 2),
        "kept_special": sorted(KEEP_EXACT_FILES),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
