"""
Zotero MCP - Model Context Protocol server for Zotero

This module provides tools for AI assistants to interact with Zotero libraries.
"""

from ._version import __version__

__all__ = ["__version__", "mcp"]


def __getattr__(name: str):
    """Lazy package attributes.

    Importing ``zotero_mcp`` happens before any ``python -m zotero_mcp.*``
    command is executed. Loading the FastMCP server here would register every
    tool and pull in optional heavy dependencies before the CLI can decide what
    it actually needs. Keep the package import light and only create the server
    when callers explicitly ask for ``zotero_mcp.mcp``.
    """
    if name == "mcp":
        from .server import mcp

        return mcp
    raise AttributeError(f"module 'zotero_mcp' has no attribute {name!r}")
