"""Subprocess entry point for crash-isolated semantic search operations."""

from __future__ import annotations

import io
import json
import sys
import traceback
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any


def _configure_stdio() -> None:
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except AttributeError:
                pass


def _read_payload() -> dict[str, Any]:
    try:
        raw = sys.stdin.read()
        return json.loads(raw or "{}")
    except Exception as exc:
        return {"operation": "", "_payload_error": f"{type(exc).__name__}: {exc}"}


def _tail(text: str, max_chars: int = 4000) -> str:
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def _run(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("_payload_error"):
        return {"ok": False, "error": payload["_payload_error"]}

    operation = payload.get("operation")
    config_path = payload.get("config_path") or str(Path.home() / ".config" / "zotero-mcp" / "config.json")
    db_path = payload.get("db_path")

    from zotero_mcp.semantic_search import create_semantic_search

    search = create_semantic_search(config_path, db_path=db_path)

    if operation == "search":
        return {
            "ok": True,
            "result": search.search(
                query=payload.get("query", ""),
                limit=int(payload.get("limit") or 10),
                filters=payload.get("filters"),
            ),
        }
    if operation == "status":
        return {"ok": True, "result": search.get_database_status()}
    if operation == "update":
        return {
            "ok": True,
            "result": search.update_database(
                force_full_rebuild=bool(payload.get("force_rebuild", False)),
                limit=payload.get("limit"),
                extract_fulltext=bool(payload.get("extract_fulltext", False)),
            ),
        }

    return {"ok": False, "error": f"Unknown semantic operation: {operation!r}"}


def main() -> int:
    _configure_stdio()
    payload = _read_payload()
    captured_stdout = io.StringIO()
    try:
        with redirect_stdout(captured_stdout):
            response = _run(payload)
    except BaseException as exc:  # keep worker failures as data when possible
        response = {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": _tail(traceback.format_exc()),
        }

    stdout_text = captured_stdout.getvalue()
    if stdout_text:
        response["captured_stdout_tail"] = _tail(stdout_text)

    sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")))
    sys.stdout.flush()
    return 0 if response.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
