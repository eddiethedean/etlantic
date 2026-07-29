"""Dialect helpers for identifier quoting and dialect detection."""

from __future__ import annotations

import re

from etlantic.sql.helpers import require_safe_identifier
from etlantic_sql.dialect_tiers import DialectInfo, detect_dialect_info

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def detect_dialect(url: str) -> str:
    """Return the normalized dialect name for ``url``."""
    return detect_dialect_info(url).name


def dialect_info(url: str) -> DialectInfo:
    """Return full dialect tier metadata for ``url``."""
    return detect_dialect_info(url)


def quote_identifier(name: str, *, dialect: str = "postgresql") -> str:
    """Quote a validated SQL identifier (double-quotes for PG and SQLite)."""
    require_safe_identifier(name)
    _ = dialect  # both Tier A reference dialects use ANSI double-quotes
    return f'"{name}"'


def is_safe_ident(name: str) -> bool:
    return bool(_IDENT.fullmatch(name))
