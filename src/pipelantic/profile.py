"""Execution profiles that bind logical pipelines to environments."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from pipelantic.secrets import SecretRef


@dataclass(frozen=True, slots=True)
class Profile:
    """Environment binding for planning without changing logical semantics."""

    name: str
    orchestrator: str = "local"
    dataframe_engine: str | None = "local"
    sql_engine: str | None = None
    allow_trusted_sql: bool = False
    bindings: dict[str, str] = field(default_factory=dict)
    implementation_overrides: dict[str, str] = field(default_factory=dict)
    secret_providers: dict[str, str] = field(default_factory=dict)
    resources: dict[str, str] = field(default_factory=dict)
    secrets: dict[str, SecretRef] = field(default_factory=dict)
    security_domain: str = "default"
    validation_policy: str = "default"
    concurrency: int | None = None
    timeout_seconds: float | None = None
    retry_max_attempts: int | None = None
    required_sql_capabilities: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def identity(self) -> str:
        """Stable profile identity."""
        return f"profile:{self.name}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize profile to a JSON-friendly dict (secret-free refs only)."""
        data = asdict(self)
        data["secrets"] = {
            key: ref.to_dict() if isinstance(ref, SecretRef) else ref
            for key, ref in self.secrets.items()
        }
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Profile:
        """Deserialize a profile mapping."""
        secrets_raw = data.get("secrets") or {}
        secrets = {
            str(k): SecretRef.from_dict(v) if isinstance(v, dict) else v
            for k, v in secrets_raw.items()
        }
        return cls(
            name=str(data["name"]),
            orchestrator=str(data.get("orchestrator") or "local"),
            dataframe_engine=data.get("dataframe_engine", "local"),
            sql_engine=data.get("sql_engine"),
            allow_trusted_sql=bool(data.get("allow_trusted_sql", False)),
            bindings=dict(data.get("bindings") or {}),
            implementation_overrides=dict(data.get("implementation_overrides") or {}),
            secret_providers=dict(data.get("secret_providers") or {}),
            resources=dict(data.get("resources") or {}),
            secrets=secrets,
            security_domain=str(data.get("security_domain") or "default"),
            validation_policy=str(data.get("validation_policy") or "default"),
            concurrency=data.get("concurrency"),
            timeout_seconds=data.get("timeout_seconds"),
            retry_max_attempts=data.get("retry_max_attempts"),
            required_sql_capabilities=tuple(
                str(x) for x in (data.get("required_sql_capabilities") or ())
            ),
            metadata=dict(data.get("metadata") or {}),
        )

    def with_updates(self, **kwargs: Any) -> Profile:
        """Return a copy with selected fields replaced."""
        current = self.to_dict()
        current.update(kwargs)
        return Profile.from_dict(current)


def development_profile(**overrides: Any) -> Profile:
    """Built-in development profile template."""
    base = Profile(
        name="development",
        orchestrator="local",
        dataframe_engine="local",
        security_domain="dev",
        validation_policy="default",
    )
    return base.with_updates(**overrides) if overrides else base


def test_profile(**overrides: Any) -> Profile:
    """Built-in test profile template."""
    base = Profile(
        name="test",
        orchestrator="local",
        dataframe_engine="local",
        security_domain="test",
        validation_policy="strict",
    )
    return base.with_updates(**overrides) if overrides else base


def production_profile(**overrides: Any) -> Profile:
    """Built-in production profile template."""
    base = Profile(
        name="production",
        orchestrator="local",
        dataframe_engine="local",
        security_domain="production",
        validation_policy="strict",
    )
    return base.with_updates(**overrides) if overrides else base


PROFILE_TEMPLATES: dict[str, Profile] = {
    "development": development_profile(),
    "dev": development_profile(),
    "local": development_profile(name="local"),
    "test": test_profile(),
    "production": production_profile(),
    "prod": production_profile(),
}


def resolve_profile(profile: str | Profile | None) -> Profile:
    """Resolve a profile name or object to a concrete Profile."""
    if profile is None:
        return development_profile(name="local")
    if isinstance(profile, Profile):
        return profile
    key = str(profile)
    if key in PROFILE_TEMPLATES:
        template = PROFILE_TEMPLATES[key]
        if key in {"local", "dev", "prod"}:
            return template
        return template
    return Profile(name=key)


def write_profile(profile: Profile, path: str | Path) -> Path:
    """Write a profile as JSON."""
    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(
        json.dumps(profile.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return resolved


def load_profile(path: str | Path) -> Profile:
    """Load a profile from a JSON file."""
    from pipelantic.interchange.security import read_text_bounded

    _resolved, text = read_text_bounded(path)
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Profile document must be a JSON object")
    return Profile.from_dict(data)
