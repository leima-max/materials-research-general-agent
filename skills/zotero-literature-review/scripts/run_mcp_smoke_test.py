#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smoke test for Zotero MCP read operations used by literature reviews."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


def default_server() -> tuple[Path, list[str], dict[str, str]]:
    workspace = Path(__file__).resolve().parents[2].parent
    server_dir = workspace / "mcp" / "zotero-mcp-server"
    python_exe = server_dir / ".venv" / "Scripts" / "python.exe"
    # Backward-compatible fallback for older layouts.
    if not python_exe.exists():
        legacy = workspace / "skills" / "zotero-mcp-server" / ".venv" / "Scripts" / "python.exe"
        if legacy.exists():
            python_exe = legacy
    if not python_exe.exists():
        python_exe = Path(os.environ.get("ZOTERO_MCP_PYTHON", "python"))
    db_path = os.environ.get("ZOTERO_DB_PATH", str(Path.home() / "Zotero" / "zotero.sqlite"))
    env = {
        "ZOTERO_LOCAL": os.environ.get("ZOTERO_LOCAL", "true"),
        "ZOTERO_LIBRARY_ID": os.environ.get("ZOTERO_LIBRARY_ID", "0"),
        "ZOTERO_LIBRARY_TYPE": os.environ.get("ZOTERO_LIBRARY_TYPE", "user"),
        "ZOTERO_NO_CLAUDE": os.environ.get("ZOTERO_NO_CLAUDE", "true"),
        "ZOTERO_DB_PATH": db_path,
        "PYTHONUTF8": os.environ.get("PYTHONUTF8", "1"),
        "PYTHONIOENCODING": os.environ.get("PYTHONIOENCODING", "utf-8"),
        "FASTMCP_SHOW_SERVER_BANNER": os.environ.get("FASTMCP_SHOW_SERVER_BANNER", "false"),
        "FASTMCP_CHECK_FOR_UPDATES": os.environ.get("FASTMCP_CHECK_FOR_UPDATES", "off"),
        "FASTMCP_ENABLE_RICH_LOGGING": os.environ.get("FASTMCP_ENABLE_RICH_LOGGING", "false"),
        "FASTMCP_ENABLE_RICH_TRACEBACKS": os.environ.get("FASTMCP_ENABLE_RICH_TRACEBACKS", "false"),
        "FASTMCP_LOG_LEVEL": os.environ.get("FASTMCP_LOG_LEVEL", "ERROR"),
        "NO_COLOR": os.environ.get("NO_COLOR", "1"),
        "TERM": os.environ.get("TERM", "dumb"),
    }
    return python_exe, ["-m", "zotero_mcp.cli", "serve"], env


async def call_tool(session: ClientSession, tool_name: str, arguments: dict[str, object]) -> dict[str, object]:
    try:
        result = await session.call_tool(tool_name, arguments)
        text = "\n".join(getattr(item, "text", "") for item in result.content)
        return {"name": tool_name, "pass": True, "chars": len(text), "sample": text[:240]}
    except Exception as exc:
        return {"name": tool_name, "pass": False, "error": f"{type(exc).__name__}: {exc}"}


async def main_async() -> int:
    command, args, env = default_server()
    params = StdioServerParameters(command=str(command), args=args, env=env)
    checks: list[dict[str, object]] = []
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = {tool.name for tool in tools.tools}
            required = {
                "zotero_get_recent",
                "zotero_search_items",
                "zotero_get_collections",
                "zotero_get_tags",
                "zotero_get_item_metadata",
                "zotero_get_item_children",
            }
            checks.append({
                "name": "list_tools",
                "pass": required.issubset(names),
                "tool_count": len(names),
                "missing": sorted(required - names),
            })
            checks.append(await call_tool(session, "zotero_get_recent", {"limit": 3}))
            checks.append(await call_tool(session, "zotero_search_items", {"query": "perovskite", "limit": 3}))
            checks.append(await call_tool(session, "zotero_get_collections", {}))
            checks.append(await call_tool(session, "zotero_get_tags", {"limit": 20}))

    ok = all(item.get("pass") for item in checks)
    print(json.dumps({"status": "ok" if ok else "error", "checks": checks}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
