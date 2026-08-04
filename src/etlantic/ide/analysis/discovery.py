"""Workspace discovery for ETLantic projects (0.44)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_IGNORE_DIR_NAMES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        "dist",
        "build",
        "site",
        ".etlantic",
        "history",
        ".benchmarks",
        ".hypothesis",
        "editors",
    }
)


@dataclass(frozen=True, slots=True)
class ProjectRoot:
    """A discovered ETLantic project root."""

    root: Path
    name: str
    has_pyproject: bool = False
    has_etlantic_dir: bool = False
    default_profile: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "name": self.name,
            "has_pyproject": self.has_pyproject,
            "has_etlantic_dir": self.has_etlantic_dir,
            "default_profile": self.default_profile,
        }


@dataclass
class WorkspaceDiscovery:
    """Discover project roots and source files under a workspace."""

    root: Path
    ignore_names: frozenset[str] = field(default_factory=lambda: _IGNORE_DIR_NAMES)
    max_files: int = 10_000

    def discover_projects(self) -> list[ProjectRoot]:
        root = self.root.resolve()
        projects: list[ProjectRoot] = []
        seen: set[Path] = set()

        def consider(path: Path) -> None:
            if path in seen:
                return
            pyproject = path / "pyproject.toml"
            etlantic_dir = path / ".etlantic"
            if pyproject.is_file() or etlantic_dir.is_dir():
                seen.add(path)
                profile = None
                profiles = path / "profiles"
                if profiles.is_dir():
                    for candidate in ("development.toml", "local.toml", "default.toml"):
                        if (profiles / candidate).is_file():
                            profile = candidate.removesuffix(".toml")
                            break
                projects.append(
                    ProjectRoot(
                        root=path,
                        name=path.name,
                        has_pyproject=pyproject.is_file(),
                        has_etlantic_dir=etlantic_dir.is_dir(),
                        default_profile=profile,
                    )
                )

        consider(root)
        for path in root.rglob("*"):
            if not path.is_dir():
                continue
            if any(part in self.ignore_names for part in path.parts):
                continue
            consider(path)
        if not projects:
            projects.append(ProjectRoot(root=root, name=root.name, has_pyproject=False))
        return projects

    def iter_source_files(self) -> list[Path]:
        root = self.root.resolve()
        files: list[Path] = []
        for path in root.rglob("*"):
            if any(part in self.ignore_names for part in path.parts):
                continue
            if not path.is_file():
                continue
            if path.suffix.lower() in {".py", ".json", ".yaml", ".yml", ".toml"}:
                files.append(path)
                if len(files) >= self.max_files:
                    break
        return files
