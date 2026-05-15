"""Crash-isolated helpers for semantic search operations.

ChromaDB and its local embedding stack can occasionally terminate the Python
process on Windows (for example in ONNX runtime code). Tool handlers must not
import or execute that stack in the MCP server process. These helpers run the
semantic operation in a child interpreter and return structured errors instead
of letting a native crash close the MCP transport.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


DEFAULT_TIMEOUTS = {
    "search": 90,
    "status": 45,
    "update": 1800,
}


def _tail(text: str | None, max_chars: int = 4000) -> str:
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def _worker_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUNBUFFERED": "1",
            "TOKENIZERS_PARALLELISM": "false",
            "FASTMCP_SHOW_SERVER_BANNER": "false",
            "FASTMCP_CHECK_FOR_UPDATES": "off",
            "FASTMCP_ENABLE_RICH_LOGGING": "false",
            "FASTMCP_ENABLE_RICH_TRACEBACKS": "false",
            "FASTMCP_LOG_LEVEL": "ERROR",
            "NO_COLOR": "1",
            "TERM": "dumb",
        }
    )
    return env


def run_semantic_operation(
    operation: str,
    *,
    config_path: str | Path | None = None,
    timeout: int | None = None,
    **payload: Any,
) -> dict[str, Any]:
    """Run a semantic-search operation in a child Python process."""
    if config_path is None:
        config_path = Path.home() / ".config" / "zotero-mcp" / "config.json"

    request = {
        "operation": operation,
        "config_path": str(config_path),
        **payload,
    }
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "zotero_mcp.semantic_worker"],
            input=json.dumps(request, ensure_ascii=False),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=_worker_env(),
            timeout=timeout or DEFAULT_TIMEOUTS.get(operation, 120),
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "error": f"Semantic {operation} timed out after {exc.timeout} seconds",
            "stderr": _tail(exc.stderr if isinstance(exc.stderr, str) else None),
            "stdout": _tail(exc.stdout if isinstance(exc.stdout, str) else None),
        }
    except Exception as exc:
        return {"ok": False, "error": f"Could not start semantic worker: {type(exc).__name__}: {exc}"}

    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    try:
        response = json.loads(stdout)
    except json.JSONDecodeError:
        response = {
            "ok": False,
            "error": "Semantic worker returned non-JSON output",
            "stdout": _tail(stdout),
        }

    if completed.returncode != 0 and response.get("ok", False):
        response["ok"] = False
        response["error"] = f"Semantic worker exited with code {completed.returncode}"

    if completed.returncode != 0:
        response.setdefault("error", f"Semantic worker exited with code {completed.returncode}")
        response["returncode"] = completed.returncode

    if stderr:
        response["stderr_tail"] = _tail(stderr)

    return response


def semantic_error_message(response: dict[str, Any]) -> str:
    """Return a concise, user-facing semantic backend error message."""
    error = response.get("error") or "unknown error"
    code = response.get("returncode")
    if code is not None:
        error = f"{error} (exit code {code})"
    stderr = response.get("stderr_tail")
    if stderr:
        last_line = [line for line in stderr.splitlines() if line.strip()]
        if last_line:
            error = f"{error}; last stderr: {last_line[-1]}"
    return error
