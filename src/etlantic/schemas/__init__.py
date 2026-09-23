# pyright: reportUnknownVariableType=false
"""Bundled JSON Schema helpers."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any


def load_schema(name: str) -> dict[str, Any]:
    """Load a packaged JSON schema by file name."""
    package = resources.files("etlantic.schemas")
    text = (package / name).read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"Schema {name} must be a JSON object")
    return data


def schema_path(name: str) -> Path:
    """Return a filesystem path to a packaged schema when available."""
    package = resources.files("etlantic.schemas")
    return Path(str(package / name))


def available_schemas() -> tuple[str, ...]:
    """Return packaged schema file names."""
    package = resources.files("etlantic.schemas")
    return tuple(
        sorted(p.name for p in package.iterdir() if p.name.endswith(".schema.json"))
    )
