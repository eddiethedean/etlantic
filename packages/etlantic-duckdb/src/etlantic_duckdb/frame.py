"""Small row-backed frame used at explicit portable conformance boundaries."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DuckDBFrame:
    rows: list[dict[str, Any]] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    column_types: dict[str, str] = field(default_factory=dict)

    def to_dicts(self) -> list[dict[str, Any]]:
        return list(self.rows)
