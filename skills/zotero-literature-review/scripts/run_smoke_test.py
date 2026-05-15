#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smoke test for local Zotero availability."""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


def default_paths() -> dict[str, Path]:
    appdata = Path(os.environ.get("APPDATA", ""))
    userprofile = Path(os.environ.get("USERPROFILE", ""))
    profile_root = appdata / "Zotero" / "Zotero"
    return {
        "zotero_exe": Path(os.environ.get("ZOTERO_EXE", r"C:\Program Files\Zotero\zotero.exe")),
        "profiles_ini": profile_root / "profiles.ini",
        "default_data_dir": Path(os.environ.get("ZOTERO_DATA_DIR", str(userprofile / "Zotero"))),
    }


def read_profile_path(profiles_ini: Path) -> Path | None:
    if not profiles_ini.exists():
        return None
    text = profiles_ini.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"^Path=(.+)$", text, flags=re.MULTILINE)
    if not match:
        return None
    raw = match.group(1).strip().replace("/", os.sep)
    return profiles_ini.parent / raw


def read_data_dir(profile_dir: Path | None, fallback: Path) -> Path:
    if not profile_dir:
        return fallback
    prefs = profile_dir / "prefs.js"
    if not prefs.exists():
        return fallback
    text = prefs.read_text(encoding="utf-8", errors="replace")
    use_data_dir = 'user_pref("extensions.zotero.useDataDir", true)' in text
    match = re.search(r'user_pref\("extensions\.zotero\.dataDir",\s*"([^"]+)"\);', text)
    if use_data_dir and match:
        return Path(match.group(1).replace("\\\\", "\\"))
    return fallback


def connect_readonly(db_path: Path) -> sqlite3.Connection:
    """Open Zotero's SQLite DB without blocking on a running Zotero process."""
    uri = f"file:{db_path.as_posix()}?mode=ro&immutable=1"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=10)
        conn.execute("pragma query_only=ON")
        return conn
    except sqlite3.OperationalError as exc:
        if "locked" not in str(exc).lower():
            raise

    tmpdir = tempfile.TemporaryDirectory(prefix="zotero_smoke_")
    tmp_db = Path(tmpdir.name) / "zotero.sqlite"
    shutil.copy2(db_path, tmp_db)
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(db_path) + suffix)
        if sidecar.exists():
            shutil.copy2(sidecar, Path(str(tmp_db) + suffix))
    conn = sqlite3.connect(f"file:{tmp_db.as_posix()}?mode=ro", uri=True, timeout=10)
    conn.execute("pragma query_only=ON")
    conn._zotero_smoke_tmpdir = tmpdir  # type: ignore[attr-defined]
    return conn


def inspect_database(db_path: Path) -> dict[str, object]:
    if not db_path.exists():
        return {"exists": False}
    conn = connect_readonly(db_path)
    try:
        cur = conn.cursor()
        tables = {row[0] for row in cur.execute("select name from sqlite_master where type='table'")}
        result: dict[str, object] = {
            "exists": True,
            "path": str(db_path),
            "size_bytes": db_path.stat().st_size,
            "has_items_table": "items" in tables,
            "has_collections_table": "collections" in tables,
        }
        if "items" in tables:
            result["item_count"] = cur.execute("select count(*) from items").fetchone()[0]
        if "collections" in tables:
            result["collection_count"] = cur.execute("select count(*) from collections").fetchone()[0]
        return result
    finally:
        conn.close()


def main() -> int:
    paths = default_paths()
    profile_dir = read_profile_path(paths["profiles_ini"])
    data_dir = read_data_dir(profile_dir, paths["default_data_dir"])
    db_info = inspect_database(data_dir / "zotero.sqlite")

    checks = [
        {"name": "zotero_exe_exists", "pass": paths["zotero_exe"].exists(), "path": str(paths["zotero_exe"])},
        {"name": "profiles_ini_exists", "pass": paths["profiles_ini"].exists(), "path": str(paths["profiles_ini"])},
        {"name": "profile_dir_exists", "pass": bool(profile_dir and profile_dir.exists()), "path": str(profile_dir) if profile_dir else None},
        {"name": "data_dir_exists", "pass": data_dir.exists(), "path": str(data_dir)},
        {"name": "zotero_sqlite_readable", "pass": bool(db_info.get("exists") and db_info.get("has_items_table")), "path": str(data_dir / "zotero.sqlite")},
    ]
    ok = all(item["pass"] for item in checks)
    result = {
        "status": "ok" if ok else "error",
        "checks": checks,
        "profile_dir": str(profile_dir) if profile_dir else None,
        "data_dir": str(data_dir),
        "database": db_info,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
