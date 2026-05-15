"""FastMCP application instance and server lifecycle."""

import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta
from pathlib import Path

from fastmcp import FastMCP

from zotero_mcp import safe_semantic as _safe_semantic
from zotero_mcp.utils import is_local_mode

# Configure logging from environment variable
# Set ZOTERO_MCP_LOG_LEVEL=DEBUG in Claude Desktop config to enable debug logs
_log_level = os.environ.get("ZOTERO_MCP_LOG_LEVEL", "WARNING").upper()
logging.basicConfig(
    level=getattr(logging, _log_level, logging.WARNING),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stderr,
)


def _semantic_auto_update_due(config_path: Path) -> bool:
    """Check semantic auto-update config without importing ChromaDB."""
    if not config_path.exists():
        return False

    try:
        with config_path.open(encoding="utf-8") as f:
            config = json.load(f)
    except Exception as exc:
        sys.stderr.write(f"Warning: Could not read semantic search config: {exc}\n")
        return False

    update_config = config.get("semantic_search", {}).get("update_config", {})
    if not update_config.get("auto_update", False):
        return False

    frequency = update_config.get("update_frequency", "manual")
    if frequency == "manual":
        return False
    if frequency == "startup":
        return True

    last_update = update_config.get("last_update")
    if not last_update:
        return True

    try:
        last_update_date = datetime.fromisoformat(last_update)
    except ValueError:
        return True

    if frequency == "daily":
        return datetime.now() - last_update_date >= timedelta(days=1)
    if frequency.startswith("every_"):
        try:
            days = int(frequency.split("_", 1)[1])
        except (ValueError, IndexError):
            return False
        return datetime.now() - last_update_date >= timedelta(days=days)

    return False


@asynccontextmanager
async def server_lifespan(server: FastMCP):
    """Manage server startup and shutdown lifecycle."""
    sys.stderr.write("Starting Zotero MCP server...\n")
    background_task: asyncio.Task | None = None

    # Check for semantic search auto-update on startup
    try:
        config_path = Path.home() / ".config" / "zotero-mcp" / "config.json"

        if _semantic_auto_update_due(config_path):
            sys.stderr.write("Auto-updating semantic search database...\n")

            async def background_update():
                try:
                    response = await asyncio.to_thread(
                        _safe_semantic.run_semantic_operation,
                        "update",
                        config_path=config_path,
                        extract_fulltext=is_local_mode(),
                    )
                    if response.get("ok"):
                        stats = response.get("result") or {}
                        sys.stderr.write(
                            f"Database update completed: {stats.get('processed_items', 0)} items processed\n"
                        )
                    else:
                        sys.stderr.write(
                            "Background database update failed: "
                            f"{_safe_semantic.semantic_error_message(response)}\n"
                        )
                except Exception as e:
                    sys.stderr.write(f"Background database update failed: {e}\n")

            background_task = asyncio.create_task(background_update())

    except Exception as e:
        sys.stderr.write(f"Warning: Could not check semantic search auto-update: {e}\n")

    yield {}

    if background_task and not background_task.done():
        background_task.cancel()
        with suppress(asyncio.CancelledError):
            await background_task

    sys.stderr.write("Shutting down Zotero MCP server...\n")


# Create an MCP server (fastmcp 2.14+ no longer accepts `dependencies`)
mcp = FastMCP("Zotero", lifespan=server_lifespan)
