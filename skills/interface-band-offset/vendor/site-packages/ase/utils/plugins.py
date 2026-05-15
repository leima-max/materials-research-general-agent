"""
Utilities for plugins to ase
"""

from typing import NamedTuple


# Name is defined in the entry point
class ExternalIOFormat(NamedTuple):
    desc: str
    code: str
    module: str | None = None
    glob: str | list[str] | None = None
    ext: str | list[str] | None = None
    magic: bytes | list[bytes] | None = None
    magic_regex: bytes | None = None


class ExternalViewer(NamedTuple):
    desc: str
    module: str | None = None
    cli: bool | None = False
    fmt: str | None = None
    argv: list[str] | None = None
