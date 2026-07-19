"""Execution profiles that bind logical pipelines to environments."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Literal

from etlantic._compat import warn_profile_bindings
from etlantic.secrets import SecretRef

PortableTransformPolicy = Literal["require", "prefer", "native"]

_WARN_PROFILE_BINDINGS = True


def _normalize_assets_bindings(
    *,
    assets: dict[str, str] | None,
    bindings: dict[str, str] | None,
    warn: bool,
) -> dict[str, str]:
    """Normalize public assets=/bindings= into one logical asset→provider map."""
    assets_map = {str(k): str(v) for k, v in dict(assets or {}).items()}
    bindings_map = {str(k): str(v) for k, v in dict(bindings or {}).items()}
    if assets_map and bindings_map and assets_map != bindings_map:
        raise ValueError(
            "Profile assets and bindings disagree. Provide only assets= "
            f"(preferred) or identical maps. assets={assets_map!r} "
            f"bindings={bindings_map!r}"
        )
    if bindings_map and not assets_map and warn and _WARN_PROFILE_BINDINGS:
        warn_profile_bindings(stacklevel=4)
    return assets_map or bindings_map


@dataclass(frozen=True, slots=True, init=False)
class Profile:
    """Environment binding for planning without changing logical semantics."""

    name: str
    orchestrator: str = "local"
    dataframe_engine: str | None = "local"
    sql_engine: str | None = None
    spark_engine: str | None = None
    allow_trusted_sql: bool = False
    spark_udf_policy: str = "warn"
    spark_streaming: bool = False
    # Internal store for logical asset name → provider. Prefer ``assets=``.
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
    # Portable orchestration intents (0.8); Airflow-specific types stay in plugins.
    schedule: dict[str, Any] = field(default_factory=dict)
    execution: dict[str, Any] = field(default_factory=dict)
    required_sql_capabilities: tuple[str, ...] = ()
    required_spark_capabilities: tuple[str, ...] = ()
    required_orchestrator_capabilities: tuple[str, ...] = ()
    # Production plugin trust (0.9): names → optional version pins (e.g. ">=0.9,<1").
    # Empty allowlist means unrestricted in non-production profiles; production
    # profiles fail closed when allowlist is empty or a discovered plugin is absent.
    plugin_allowlist: dict[str, str | None] = field(default_factory=dict)
    # 0.12: portable vs native selection (no silent fallback).
    portable_transform_policy: PortableTransformPolicy = "prefer"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        name: str,
        *,
        orchestrator: str = "local",
        dataframe_engine: str | None = "local",
        sql_engine: str | None = None,
        spark_engine: str | None = None,
        allow_trusted_sql: bool = False,
        spark_udf_policy: str = "warn",
        spark_streaming: bool = False,
        bindings: dict[str, str] | None = None,
        assets: dict[str, str] | None = None,
        implementation_overrides: dict[str, str] | None = None,
        secret_providers: dict[str, str] | None = None,
        resources: dict[str, str] | None = None,
        secrets: dict[str, SecretRef] | None = None,
        security_domain: str = "default",
        validation_policy: str = "default",
        concurrency: int | None = None,
        timeout_seconds: float | None = None,
        retry_max_attempts: int | None = None,
        schedule: dict[str, Any] | None = None,
        execution: dict[str, Any] | None = None,
        required_sql_capabilities: tuple[str, ...] = (),
        required_spark_capabilities: tuple[str, ...] = (),
        required_orchestrator_capabilities: tuple[str, ...] = (),
        plugin_allowlist: dict[str, str | None] | None = None,
        portable_transform_policy: PortableTransformPolicy = "prefer",
        metadata: dict[str, Any] | None = None,
        _warn_legacy_bindings: bool = True,
    ) -> None:
        store = _normalize_assets_bindings(
            assets=assets,
            bindings=bindings,
            warn=_warn_legacy_bindings,
        )
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "orchestrator", orchestrator)
        object.__setattr__(self, "dataframe_engine", dataframe_engine)
        object.__setattr__(self, "sql_engine", sql_engine)
        object.__setattr__(self, "spark_engine", spark_engine)
        object.__setattr__(self, "allow_trusted_sql", allow_trusted_sql)
        object.__setattr__(self, "spark_udf_policy", spark_udf_policy)
        object.__setattr__(self, "spark_streaming", spark_streaming)
        object.__setattr__(self, "bindings", store)
        object.__setattr__(
            self, "implementation_overrides", dict(implementation_overrides or {})
        )
        object.__setattr__(self, "secret_providers", dict(secret_providers or {}))
        object.__setattr__(self, "resources", dict(resources or {}))
        object.__setattr__(self, "secrets", dict(secrets or {}))
        object.__setattr__(self, "security_domain", security_domain)
        object.__setattr__(self, "validation_policy", validation_policy)
        object.__setattr__(self, "concurrency", concurrency)
        object.__setattr__(self, "timeout_seconds", timeout_seconds)
        object.__setattr__(self, "retry_max_attempts", retry_max_attempts)
        object.__setattr__(self, "schedule", dict(schedule or {}))
        object.__setattr__(self, "execution", dict(execution or {}))
        object.__setattr__(
            self, "required_sql_capabilities", tuple(required_sql_capabilities)
        )
        object.__setattr__(
            self, "required_spark_capabilities", tuple(required_spark_capabilities)
        )
        object.__setattr__(
            self,
            "required_orchestrator_capabilities",
            tuple(required_orchestrator_capabilities),
        )
        object.__setattr__(self, "plugin_allowlist", dict(plugin_allowlist or {}))
        object.__setattr__(self, "portable_transform_policy", portable_transform_policy)
        object.__setattr__(self, "metadata", dict(metadata or {}))

    @property
    def assets(self) -> dict[str, str]:
        """Preferred public view of logical asset → provider resolution."""
        return dict(self.bindings)

    def identity(self) -> str:
        """Stable profile identity."""
        return f"profile:{self.name}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize profile for public JSON (assets preferred, bindings mirrored)."""
        data = asdict(self)
        data["secrets"] = {
            key: ref.to_dict() if isinstance(ref, SecretRef) else ref
            for key, ref in self.secrets.items()
        }
        asset_map = dict(self.bindings)
        data["assets"] = asset_map
        data["bindings"] = dict(asset_map)
        return data

    def to_plan_snapshot(self) -> dict[str, Any]:
        """Fingerprint-stable snapshot retaining the pre-0.15 ``bindings`` shape."""
        data = asdict(self)
        data["secrets"] = {
            key: ref.to_dict() if isinstance(ref, SecretRef) else ref
            for key, ref in self.secrets.items()
        }
        # Intentionally omit ``assets`` so equivalent plans keep fingerprints.
        data["bindings"] = dict(self.bindings)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, warn_legacy: bool = True) -> Profile:
        """Deserialize a profile mapping."""
        secrets_raw = data.get("secrets") or {}
        if not isinstance(secrets_raw, dict):
            raise ValueError("Profile secrets must be a mapping of name → SecretRef")
        secrets: dict[str, SecretRef] = {}
        for key, value in secrets_raw.items():
            if isinstance(value, SecretRef):
                secrets[str(key)] = value
            elif isinstance(value, dict):
                secrets[str(key)] = SecretRef.from_dict(value)
            else:
                raise ValueError(
                    f"Profile secret {key!r} must be a SecretRef mapping, "
                    "not a plaintext value"
                )
        has_assets = "assets" in data and data.get("assets") is not None
        has_bindings = "bindings" in data and data.get("bindings") is not None
        store = _normalize_assets_bindings(
            assets=dict(data.get("assets") or {}) if has_assets else None,
            bindings=dict(data.get("bindings") or {}) if has_bindings else None,
            warn=bool(warn_legacy and has_bindings and not has_assets),
        )
        return cls(
            name=str(data["name"]),
            orchestrator=str(data.get("orchestrator") or "local"),
            dataframe_engine=data.get("dataframe_engine", "local"),
            sql_engine=data.get("sql_engine"),
            spark_engine=data.get("spark_engine"),
            allow_trusted_sql=bool(data.get("allow_trusted_sql", False)),
            spark_udf_policy=str(data.get("spark_udf_policy") or "warn"),
            spark_streaming=bool(data.get("spark_streaming", False)),
            bindings=store,
            implementation_overrides=dict(data.get("implementation_overrides") or {}),
            secret_providers=dict(data.get("secret_providers") or {}),
            resources=dict(data.get("resources") or {}),
            secrets=secrets,
            security_domain=str(data.get("security_domain") or "default"),
            validation_policy=str(data.get("validation_policy") or "default"),
            concurrency=data.get("concurrency"),
            timeout_seconds=data.get("timeout_seconds"),
            retry_max_attempts=data.get("retry_max_attempts"),
            schedule=dict(data.get("schedule") or {}),
            execution=dict(data.get("execution") or {}),
            required_sql_capabilities=_as_str_tuple(
                data.get("required_sql_capabilities")
            ),
            required_spark_capabilities=_as_str_tuple(
                data.get("required_spark_capabilities")
            ),
            required_orchestrator_capabilities=_as_str_tuple(
                data.get("required_orchestrator_capabilities")
            ),
            plugin_allowlist={
                str(k): (None if v in (None, "") else str(v))
                for k, v in dict(data.get("plugin_allowlist") or {}).items()
            },
            portable_transform_policy=_parse_portable_policy(
                data.get("portable_transform_policy")
            ),
            metadata=dict(data.get("metadata") or {}),
            _warn_legacy_bindings=False,
        )

    def with_updates(self, **kwargs: Any) -> Profile:
        """Return a copy with selected fields replaced.

        Unknown keys raise ``TypeError`` so typos like ``plugin_allow_list``
        cannot silently leave production allowlists empty. ``assets`` is accepted
        as the preferred alias for ``bindings``.
        """
        known = {f.name for f in fields(self)} | {"assets"}
        unknown = sorted(set(kwargs) - known)
        if unknown:
            raise TypeError(
                f"Profile.with_updates() got unexpected field(s): {', '.join(unknown)}"
            )
        current = self.to_plan_snapshot()
        if "assets" in kwargs and "bindings" in kwargs:
            store = _normalize_assets_bindings(
                assets=kwargs.pop("assets"),
                bindings=kwargs.pop("bindings"),
                warn=False,
            )
            current["bindings"] = store
        elif "assets" in kwargs:
            current["bindings"] = dict(kwargs.pop("assets") or {})
        elif "bindings" in kwargs:
            if _WARN_PROFILE_BINDINGS:
                warn_profile_bindings(stacklevel=3)
            current["bindings"] = dict(kwargs.pop("bindings") or {})
        current.update(kwargs)
        return Profile.from_dict(current, warn_legacy=False)


def _as_str_tuple(value: Any) -> tuple[str, ...]:
    """Normalize capability lists without iterating bare strings by character."""
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(x) for x in value)


def _parse_portable_policy(value: Any) -> PortableTransformPolicy:
    policy = str(value or "prefer")
    if policy not in {"require", "prefer", "native"}:
        raise ValueError(
            f"portable_transform_policy must be require|prefer|native, got {policy!r}"
        )
    return policy  # type: ignore[return-value]


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
    """Resolve a profile name, JSON path, or object to a concrete Profile.

    When ``profile`` is a string ending in ``.json`` that exists as a file,
    the profile is loaded with :func:`load_profile`. Built-in template names
    (``development``, ``production``, …) resolve to templates. Other bare
    names create an empty :class:`Profile` with that name.
    """
    if profile is None:
        return development_profile(name="local")
    if isinstance(profile, Profile):
        return profile
    key = str(profile)
    path = Path(key)
    if path.suffix.casefold() == ".json":
        if not path.is_file():
            raise FileNotFoundError(f"Profile JSON path not found: {path}")
        return load_profile(path)
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
    from etlantic.interchange.security import read_text_bounded

    _resolved, text = read_text_bounded(path)
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Profile document must be a JSON object")
    return Profile.from_dict(data)
