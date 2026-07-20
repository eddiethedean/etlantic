"""Durable workspace layout for ETLantic projects."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class WorkspacePaths:
    """Resolved workspace directory layout."""

    root: Path
    reports: Path
    artifacts: Path
    schema_history: Path
    data: Path


def discover_project_root(start: Path | None = None) -> Path | None:
    """Walk up from *start* looking for ``etlantic.toml``."""
    current = (start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        if (directory / "etlantic.toml").is_file():
            return directory
    return None


def resolve_workspace(
    *,
    workspace: str | Path | None = None,
    start: Path | None = None,
) -> WorkspacePaths:
    """Resolve workspace paths for CLI and SDK use.

    Discovery order:
    1. Explicit *workspace* argument
    2. ``ETLANTIC_WORKSPACE`` environment variable
    3. Parent directory of discovered ``etlantic.toml``
    4. Current working directory
    """
    if workspace is not None:
        root = Path(workspace).expanduser().resolve()
    elif env := os.environ.get("ETLANTIC_WORKSPACE"):
        root = Path(env).expanduser().resolve()
    elif project := discover_project_root(start):
        root = project
    else:
        root = (start or Path.cwd()).resolve()

    etlantic_dir = root / ".etlantic"
    return WorkspacePaths(
        root=root,
        reports=etlantic_dir / "reports",
        artifacts=etlantic_dir / "artifacts",
        schema_history=etlantic_dir / "schema-history",
        data=root / "data",
    )


def ensure_workspace_layout(paths: WorkspacePaths) -> None:
    """Create standard workspace directories if missing."""
    for directory in (
        paths.reports,
        paths.artifacts,
        paths.schema_history,
        paths.data,
    ):
        directory.mkdir(parents=True, exist_ok=True)
