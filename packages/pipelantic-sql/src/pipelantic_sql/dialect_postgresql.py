"""Dialect helpers for identifier quoting and dialect detection."""

from __future__ import annotations

import re

from pipelantic.sql.helpers import require_safe_identifier

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def detect_dialect(url: str) -> str:
    if url.startswith("postgresql"):
        return "postgresql"
    return "sqlite"


def quote_identifier(name: str, *, dialect: str = "postgresql") -> str:
    """Quote a validated SQL identifier (double-quotes for PG and SQLite)."""
    require_safe_identifier(name)
    _ = dialect  # both reference dialects use ANSI double-quotes
    return f'"{name}"'


def is_safe_ident(name: str) -> bool:
    return bool(_IDENT.fullmatch(name))
