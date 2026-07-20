"""Optional etlantic.toml project configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from etlantic.profile import Profile, load_profile, resolve_profile
from etlantic.workspace import discover_project_root


@dataclass(frozen=True, slots=True)
class ProjectConfig:
    """Resolved project configuration."""

    root: Path
    name: str | None
    default_profile: str
    profiles: dict[str, Profile] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    config_path: Path | None = None


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover - py311+
        raise RuntimeError("tomllib is required (Python 3.11+)") from None
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("etlantic.toml must be a TOML table")
    return data


def _resolve_profile_ref(
    ref: str | dict[str, Any],
    *,
    root: Path,
    accept_legacy_bindings: bool = False,
) -> Profile:
    if isinstance(ref, dict):
        return Profile.from_dict(ref, accept_legacy_bindings=accept_legacy_bindings)
    text = str(ref).strip()
    if text.endswith(".json"):
        path = (root / text).resolve() if not Path(text).is_absolute() else Path(text)
        if path.is_file():
            return load_profile(path)
    path = root / "profiles" / f"{text}.json"
    if path.is_file():
        return load_profile(path)
    return resolve_profile(text)


def load_project(start: Path | None = None) -> ProjectConfig | None:
    """Load project config when ``etlantic.toml`` exists."""
    root = discover_project_root(start)
    if root is None:
        return None
    config_path = root / "etlantic.toml"
    data = _load_toml(config_path)
    profiles_raw = data.get("profiles") or {}
    profiles: dict[str, Profile] = {}
    if isinstance(profiles_raw, dict):
        for name, ref in profiles_raw.items():
            profiles[str(name)] = _resolve_profile_ref(ref, root=root)
    default_profile = str(data.get("default_profile") or "development")
    return ProjectConfig(
        root=root,
        name=data.get("project"),
        default_profile=default_profile,
        profiles=profiles,
        metadata=dict(data.get("metadata") or {}),
        config_path=config_path,
    )


def resolve_project_profile(
    profile_name: str | None,
    *,
    start: Path | None = None,
    allow_adhoc_profile: bool = False,
    accept_legacy_bindings: bool = False,
) -> tuple[Profile, str]:
    """Resolve profile using project config, profiles/, and built-ins.

    Returns:
        Tuple of (profile, source description).
    """
    project = load_project(start)
    name = profile_name
    if name is None and project is not None:
        name = project.default_profile

    if project is not None and name in project.profiles:
        return project.profiles[name], f"etlantic.toml profiles.{name}"

    root = project.root if project is not None else (start or Path.cwd())
    profiles_path = root / "profiles" / f"{name}.json"
    if name and profiles_path.is_file():
        return load_profile(profiles_path), str(profiles_path)

    if name and Path(name).suffix.casefold() == ".json" and Path(name).is_file():
        return load_profile(name), str(Path(name).resolve())

    resolved = resolve_profile(name, allow_adhoc_profile=allow_adhoc_profile)
    if name in {"development", "dev", "local", "test", "production", "prod"}:
        return resolved, f"builtin:{name}"
    if allow_adhoc_profile and name:
        return resolved, f"adhoc:{name}"
    return resolved, f"resolved:{resolved.name}"


def project_config_to_dict(config: ProjectConfig) -> dict[str, Any]:
    return {
        "project": config.name,
        "default_profile": config.default_profile,
        "profiles": {
            name: profile.to_dict() for name, profile in config.profiles.items()
        },
        "metadata": dict(config.metadata),
        "root": str(config.root),
        "config_path": str(config.config_path) if config.config_path else None,
    }


def write_minimal_etlantic_toml(
    path: Path,
    *,
    project: str,
    default_profile: str = "development",
) -> Path:
    """Write a minimal etlantic.toml scaffold."""
    text = (
        f'project = "{project}"\n'
        f'default_profile = "{default_profile}"\n'
        "\n"
        "[metadata]\n"
        'etlantic.version = "0.21"\n'
    )
    path.write_text(text, encoding="utf-8")
    return path.resolve()
