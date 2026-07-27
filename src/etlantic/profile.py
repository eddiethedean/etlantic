"""Execution profiles that bind logical pipelines to environments."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Literal

from etlantic.secrets import SecretRef

PortableTransformPolicy = Literal["require", "prefer", "native"]
SecurityMode = Literal["development", "test", "production"]

_BINDINGS_REMOVED = (
    "Profile(bindings=...) was removed in ETLantic 0.16. Use assets= instead. "
    "See docs/11_DEVELOPMENT/MIGRATION_0_15_TO_0_16.md."
)
_LEGACY_BINDINGS_REJECTED = (
    "PMCFG111: Profile JSON used legacy 'bindings'. Rename to 'assets' or pass "
    "--accept-legacy-bindings / accept_legacy_bindings=True."
)
_UNKNOWN_PROFILE = (
    "PMCFG100: Unknown profile name {name!r}. Use a built-in template "
    "(development, local, test, production), a .json path, or pass "
    "allow_adhoc_profile=True / --allow-adhoc-profile."
)


def _normalize_assets(
    *,
    assets: dict[str, Any] | None,
    bindings: dict[str, Any] | None = None,
    allow_legacy_bindings: bool = False,
) -> dict[str, str]:
    """Normalize public assets= into the internal asset→provider store."""
    from etlantic.bindings import normalize_assets_map

    assets_map = normalize_assets_map(dict(assets or {})) if assets else {}
    bindings_map = normalize_assets_map(dict(bindings or {})) if bindings else {}
    if bindings_map and not allow_legacy_bindings:
        raise TypeError(_BINDINGS_REMOVED)
    if assets_map and bindings_map and assets_map != bindings_map:
        raise ValueError(
            "Profile assets and bindings disagree. Provide only assets=. "
            f"assets={assets_map!r} bindings={bindings_map!r}"
        )
    # Prefer non-empty assets; never let empty assets unlock legacy bindings.
    if assets_map:
        return assets_map
    return bindings_map


@dataclass(frozen=True, slots=True, init=False)
class Profile:
    """Environment binding for planning and execution without changing logic.

    A profile selects engines (local Python, Polars, SQL, PySpark, …), maps
    logical ``asset`` names to storage providers, and carries trust and policy
    settings. The same :class:`~etlantic.pipeline.Pipeline` class can be
    validated, planned, and run under different profiles.

    Important fields:

    - ``assets`` (public) / internal ``bindings``: logical asset → provider id
    - ``dataframe_engine``, ``sql_engine``, ``spark_engine``: engine selection
    - ``security_mode``: ``development``, ``test``, or ``production``
    - ``plugin_allowlist``: production fail-closed plugin trust (name → pin)
    - ``portable_transform_policy``: ``prefer``, ``require``, or ``native``
    - ``safe_io``, ``outbound``: 0.20 safe I/O and outbound HTTP policy

    Production profiles with ``security_mode="production"`` require a non-empty
    ``plugin_allowlist`` and readable static plugin manifests before import.

    Use :func:`development_profile`, :func:`test_profile`, or
    :func:`production_profile` as templates, or resolve names and JSON paths
    with :func:`resolve_profile`.
    """

    name: str
    orchestrator: str = "local"
    dataframe_engine: str | None = "local"
    sql_engine: str | None = None
    spark_engine: str | None = None
    allow_trusted_sql: bool = False
    spark_udf_policy: str = "warn"
    spark_streaming: bool = False
    # Internal store for logical asset name → provider (plan wire name: bindings).
    bindings: dict[str, str] = field(default_factory=dict)
    implementation_overrides: dict[str, str] = field(default_factory=dict)
    secret_providers: dict[str, str] = field(default_factory=dict)
    resources: dict[str, str] = field(default_factory=dict)
    secrets: dict[str, SecretRef] = field(default_factory=dict)
    security_domain: str = "default"
    security_mode: SecurityMode = "development"
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
    # 0.20: safe I/O, outbound, isolation, optional capability probe.
    tenant: str = "default"
    environment: str = "default"
    safe_io: dict[str, Any] = field(default_factory=dict)
    outbound: dict[str, Any] = field(default_factory=dict)
    require_plugin_probe: bool = False
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
        assets: dict[str, str] | None = None,
        implementation_overrides: dict[str, str] | None = None,
        secret_providers: dict[str, str] | None = None,
        resources: dict[str, str] | None = None,
        secrets: dict[str, SecretRef] | None = None,
        security_domain: str = "default",
        security_mode: SecurityMode = "development",
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
        tenant: str = "default",
        environment: str = "default",
        safe_io: dict[str, Any] | None = None,
        outbound: dict[str, Any] | None = None,
        require_plugin_probe: bool = False,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Construct an immutable execution profile.

        Args:
            name: Profile name (also used by template resolution).
            orchestrator: Orchestrator id (default ``"local"``).
            dataframe_engine: Dataframe engine id, or ``None``.
            sql_engine: SQL engine id, or ``None``.
            spark_engine: Spark engine id, or ``None``.
            allow_trusted_sql: Whether trusted SQL paths are permitted.
            spark_udf_policy: Spark UDF policy string (e.g. ``"warn"``).
            spark_streaming: Enable Spark streaming settings when True.
            assets: Logical asset name → provider id map (public authoring key).
            implementation_overrides: Node/step → implementation id overrides.
            secret_providers: Secret provider name → backend id map.
            resources: Resource name → provider id map.
            secrets: Named :class:`~etlantic.secrets.SecretRef` values only.
            security_domain: Logical security domain label.
            security_mode: ``"development"``, ``"test"``, or ``"production"``.
            validation_policy: Validation policy name (e.g. ``"default"``).
            concurrency: Optional concurrency limit.
            timeout_seconds: Optional run timeout.
            retry_max_attempts: Optional retry attempt ceiling.
            schedule: Portable schedule intent mapping.
            execution: Portable execution intent mapping.
            required_sql_capabilities: Required SQL capability tokens.
            required_spark_capabilities: Required Spark capability tokens.
            required_orchestrator_capabilities: Required orchestrator tokens.
            plugin_allowlist: Plugin name → optional version pin (production
                fail-closed when empty under ``security_mode="production"``).
            portable_transform_policy: ``"prefer"``, ``"require"``, or
                ``"native"``.
            tenant: Tenant label for safe I/O / outbound policy.
            environment: Environment label for safe I/O / outbound policy.
            safe_io: Safe I/O policy mapping.
            outbound: Outbound HTTP policy mapping.
            require_plugin_probe: Require capability probe when True.
            metadata: Extension metadata (size/depth budgets enforced later).
            **kwargs: Rejected if it contains removed ``bindings=``.

        Raises:
            TypeError: When ``bindings=`` is passed (removed in 0.16).
            ValueError: When ``security_mode`` is not a known mode.
        """
        if "bindings" in kwargs:
            raise TypeError(_BINDINGS_REMOVED)
        store = _normalize_assets(assets=assets)
        mode = _parse_security_mode(security_mode)
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
        object.__setattr__(self, "security_mode", mode)
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
        object.__setattr__(self, "tenant", str(tenant or "default"))
        object.__setattr__(self, "environment", str(environment or "default"))
        object.__setattr__(self, "safe_io", dict(safe_io or {}))
        object.__setattr__(self, "outbound", dict(outbound or {}))
        object.__setattr__(self, "require_plugin_probe", bool(require_plugin_probe))
        object.__setattr__(self, "metadata", dict(metadata or {}))

    def primary_engine(self) -> str:
        """Resolve the profile's primary execution engine (spark → sql → dataframe).

        Returns:
            Engine id from ``spark_engine``, else ``sql_engine``, else
            ``dataframe_engine`` (defaulting to ``"local"``).
        """
        from etlantic.engines import get_engine_registry

        return get_engine_registry().primary_engine(self)

    @property
    def engine_profile(self) -> Any:
        """Internal engine configuration view.

        Returns:
            An ``EngineProfile`` record for engine registry lookups.
        """
        from etlantic._profile.records import EngineProfile

        return EngineProfile(
            dataframe_engine=self.dataframe_engine,
            sql_engine=self.sql_engine,
            spark_engine=self.spark_engine,
            orchestrator=self.orchestrator,
            allow_trusted_sql=self.allow_trusted_sql,
            spark_udf_policy=self.spark_udf_policy,
            spark_streaming=self.spark_streaming,
            required_sql_capabilities=self.required_sql_capabilities,
            required_spark_capabilities=self.required_spark_capabilities,
            required_orchestrator_capabilities=self.required_orchestrator_capabilities,
            portable_transform_policy=self.portable_transform_policy,
            implementation_overrides=dict(self.implementation_overrides),
        )

    @property
    def assets(self) -> dict[str, str]:
        """Preferred public view of logical asset → provider resolution.

        Returns:
            A shallow copy of the internal asset→provider store.
        """
        return dict(self.bindings)

    def identity(self) -> str:
        """Return the stable profile identity string.

        Returns:
            ``"profile:{name}"`` for this profile.
        """
        return f"profile:{self.name}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize profile for public JSON (assets only; no mirrored bindings).

        Returns:
            A JSON-serializable mapping using public ``assets`` (not plan-wire
            ``bindings``). Secret values remain :class:`SecretRef` dicts.
        """
        data = asdict(self)
        data["secrets"] = {
            key: ref.to_dict() if isinstance(ref, SecretRef) else ref
            for key, ref in self.secrets.items()
        }
        data["assets"] = dict(self.bindings)
        data.pop("bindings", None)
        for key in (
            "required_sql_capabilities",
            "required_spark_capabilities",
            "required_orchestrator_capabilities",
        ):
            if key in data and isinstance(data[key], tuple):
                data[key] = list(data[key])
        return data

    def to_plan_snapshot(self) -> dict[str, Any]:
        """Fingerprint-stable snapshot retaining the plan wire ``bindings`` shape.

        Returns:
            A mapping suitable for embedding in a frozen plan (uses ``bindings``
            rather than public ``assets``).
        """
        data = asdict(self)
        data["secrets"] = {
            key: ref.to_dict() if isinstance(ref, SecretRef) else ref
            for key, ref in self.secrets.items()
        }
        # Intentionally omit ``assets`` so equivalent plans keep fingerprints.
        data["bindings"] = dict(self.bindings)
        return data

    @classmethod
    def from_plan_snapshot(cls, data: dict[str, Any]) -> Profile:
        """Rehydrate a profile embedded in a frozen plan (bindings wire shape).

        Args:
            data: Plan-embedded profile snapshot (may use ``bindings``).

        Returns:
            A concrete :class:`Profile`.

        Raises:
            ValueError: When required fields or nested values are invalid
                (delegates to :meth:`from_dict`).
            KeyError: When ``name`` is missing from ``data``.
        """
        snap = dict(data)
        if "assets" not in snap and "bindings" in snap:
            snap["assets"] = dict(snap.get("bindings") or {})
        # Plan wire uses ``bindings`` intentionally; never treat as adopter JSON.
        snap.pop("bindings", None)
        return cls.from_dict(snap)

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        *,
        accept_legacy_bindings: bool = False,
    ) -> Profile:
        """Deserialize a profile mapping.

        Legacy JSON ``bindings`` keys require ``accept_legacy_bindings=True``
        in 0.21+ (use ``profile migrate`` to rewrite to ``assets``).

        Args:
            data: Profile document mapping (must include ``name``).
            accept_legacy_bindings: When True, allow legacy ``bindings`` keys
                (emits ``PMCFG110`` warning). Default fail-closed ``PMCFG111``.

        Returns:
            A concrete :class:`Profile`.

        Raises:
            ValueError: When secrets are plaintext/invalid, legacy ``bindings``
                appear without opt-in, or ``security_mode`` /
                ``portable_transform_policy`` are unknown.
            KeyError: When ``name`` is missing from ``data``.
        """
        import warnings

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
        assets_raw = data.get("assets")
        bindings_raw = data.get("bindings")
        has_assets_key = "assets" in data and assets_raw is not None
        has_bindings_key = "bindings" in data and bindings_raw is not None
        assets_map_preview = dict(assets_raw or {}) if has_assets_key else {}
        bindings_map_preview = dict(bindings_raw or {}) if has_bindings_key else {}
        # Empty assets must not unlock legacy bindings (PMCFG111).
        needs_legacy_opt_in = bool(bindings_map_preview) or (
            has_bindings_key and not assets_map_preview
        )
        if needs_legacy_opt_in:
            if not accept_legacy_bindings:
                raise ValueError(_LEGACY_BINDINGS_REJECTED)
            warnings.warn(
                "PMCFG110: legacy 'bindings' loaded; migrate to 'assets'.",
                UserWarning,
                stacklevel=2,
            )
        store = _normalize_assets(
            assets=assets_map_preview if has_assets_key else None,
            bindings=bindings_map_preview if has_bindings_key else None,
            allow_legacy_bindings=True,
        )
        security_mode = data.get("security_mode")
        if security_mode is None:
            security_mode = _infer_security_mode(
                name=str(data.get("name") or ""),
                security_domain=str(data.get("security_domain") or "default"),
            )
            warnings.warn(
                "Profile JSON omitted explicit security_mode; inferred "
                f"{security_mode!r} from name/domain. Prefer setting security_mode "
                "explicitly.",
                UserWarning,
                stacklevel=2,
            )
        mode = _parse_security_mode(security_mode)
        return cls(
            name=str(data["name"]),
            orchestrator=str(data.get("orchestrator") or "local"),
            dataframe_engine=data.get("dataframe_engine", "local"),
            sql_engine=data.get("sql_engine"),
            spark_engine=data.get("spark_engine"),
            allow_trusted_sql=bool(data.get("allow_trusted_sql", False)),
            spark_udf_policy=str(data.get("spark_udf_policy") or "warn"),
            spark_streaming=bool(data.get("spark_streaming", False)),
            assets=store,
            implementation_overrides=dict(data.get("implementation_overrides") or {}),
            secret_providers=dict(data.get("secret_providers") or {}),
            resources=dict(data.get("resources") or {}),
            secrets=secrets,
            security_domain=str(data.get("security_domain") or "default"),
            security_mode=mode,
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
            tenant=str(data.get("tenant") or "default"),
            environment=str(data.get("environment") or "default"),
            safe_io=dict(data.get("safe_io") or {}),
            outbound=dict(data.get("outbound") or {}),
            require_plugin_probe=bool(data.get("require_plugin_probe", False)),
            metadata=_validated_profile_metadata(
                data.get("metadata") or {},
                strict=mode == "production",
            ),
        )

    def with_updates(self, **kwargs: Any) -> Profile:
        """Return a copy with selected fields replaced.

        Unknown keys raise ``TypeError`` so typos like ``plugin_allow_list``
        cannot silently leave production allowlists empty. ``assets`` is the
        public authoring key for the internal bindings store.

        Args:
            **kwargs: Field replacements. Use ``assets=`` for asset maps;
                ``bindings=`` is rejected.

        Returns:
            A new :class:`Profile` with updates applied.

        Raises:
            TypeError: When ``bindings=`` is passed or unknown field names
                appear in ``kwargs``.
            ValueError: When updated values fail :meth:`from_dict` validation.
        """
        known = {f.name for f in fields(self)} | {"assets"}
        # Reject public bindings= authoring; internal snapshot still uses bindings.
        if "bindings" in kwargs:
            raise TypeError(_BINDINGS_REMOVED)
        unknown = sorted(set(kwargs) - known)
        if unknown:
            raise TypeError(
                f"Profile.with_updates() got unexpected field(s): {', '.join(unknown)}"
            )
        current = self.to_plan_snapshot()
        if "assets" in kwargs:
            current["bindings"] = dict(kwargs.pop("assets") or {})
        # Internal snapshot uses plan-wire ``bindings``; map to assets so
        # from_dict does not emit legacy PMCFG110 for authoring round-trips.
        if "bindings" in current and "assets" not in current:
            current["assets"] = dict(current.pop("bindings") or {})
        current.update(kwargs)
        return Profile.from_dict(current)


def _validated_profile_metadata(
    raw: Any, *, strict: bool | None = None
) -> dict[str, Any]:
    """Copy profile metadata and enforce extension size/depth budgets."""
    from etlantic.extensions import validate_extension_metadata

    metadata = dict(raw or {})
    if strict is None:
        strict = False
    validate_extension_metadata(metadata, path="metadata", strict=strict)
    return metadata


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


def _parse_security_mode(value: Any) -> SecurityMode:
    mode = str(value or "development").strip().lower()
    if mode not in {"development", "test", "production"}:
        raise ValueError(
            f"security_mode must be development|test|production, got {value!r}"
        )
    return mode  # type: ignore[return-value]


def _infer_security_mode(*, name: str, security_domain: str) -> SecurityMode:
    """Best-effort inference for pre-0.19 profile JSON missing security_mode."""
    key = name.strip().lower()
    domain = security_domain.strip().lower()
    if key in {"production", "prod", "staging"} or domain in {"production", "prod"}:
        return "production"
    if key == "test" or domain == "test":
        return "test"
    return "development"


def development_profile(**overrides: Any) -> Profile:
    """Return the built-in development profile template.

    Defaults: ``orchestrator="local"``, ``dataframe_engine="local"``,
    ``security_mode="development"``, ``validation_policy="default"``.

    Args:
        **overrides: Passed to :meth:`Profile.with_updates` when non-empty.

    Returns:
        A concrete :class:`Profile` instance.

    Raises:
        TypeError: When ``overrides`` contains unknown fields or ``bindings=``.
        ValueError: When override values fail profile validation.
    """
    base = Profile(
        name="development",
        orchestrator="local",
        dataframe_engine="local",
        security_domain="dev",
        security_mode="development",
        validation_policy="default",
    )
    return base.with_updates(**overrides) if overrides else base


def test_profile(**overrides: Any) -> Profile:
    """Return the built-in test profile template.

    Defaults: ``security_mode="test"``, ``validation_policy="strict"``.

    Args:
        **overrides: Passed to :meth:`Profile.with_updates` when non-empty.

    Returns:
        A concrete :class:`Profile` instance.

    Raises:
        TypeError: When ``overrides`` contains unknown fields or ``bindings=``.
        ValueError: When override values fail profile validation.
    """
    base = Profile(
        name="test",
        orchestrator="local",
        dataframe_engine="local",
        security_domain="test",
        security_mode="test",
        validation_policy="strict",
    )
    return base.with_updates(**overrides) if overrides else base


def production_profile(**overrides: Any) -> Profile:
    """Return the built-in production profile template.

    Defaults: ``security_mode="production"``, ``validation_policy="strict"``.
    Callers must still set ``plugin_allowlist`` (and usually ``assets``) before
    planning or running in production.

    Args:
        **overrides: Passed to :meth:`Profile.with_updates` when non-empty.

    Returns:
        A concrete :class:`Profile` instance.

    Raises:
        TypeError: When ``overrides`` contains unknown fields or ``bindings=``.
        ValueError: When override values fail profile validation.
    """
    base = Profile(
        name="production",
        orchestrator="local",
        dataframe_engine="local",
        security_domain="production",
        security_mode="production",
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


def resolve_profile(
    profile: str | Profile | None,
    *,
    allow_adhoc_profile: bool = False,
) -> Profile:
    """Resolve a profile name, JSON path, or object to a concrete Profile.

    Resolution order for string ``profile``:

    1. Existing ``.json`` file path → :func:`load_profile`
    2. Built-in template name (``development``, ``local``, ``test``, ``production``,
       ``prod``, ``dev``) → template from :data:`PROFILE_TEMPLATES`
    3. Unknown bare name → fail closed unless ``allow_adhoc_profile`` is True

    Args:
        profile: Template name, JSON path, :class:`Profile`, or ``None``.
            ``None`` resolves to ``development_profile(name="local")``.
        allow_adhoc_profile: When True, unknown bare names become ad hoc
            development profiles. CLI exposes this as ``--allow-adhoc-profile``.

    Returns:
        A concrete :class:`Profile`.

    Raises:
        FileNotFoundError: When ``profile`` ends with ``.json`` but the path
            does not exist.
        ValueError: When the name is unknown and ``allow_adhoc_profile`` is
            False (message includes diagnostic ``PMCFG100``).
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
    profiles_path = Path("profiles") / f"{key}.json"
    if profiles_path.is_file():
        return load_profile(profiles_path)
    if key in PROFILE_TEMPLATES:
        return PROFILE_TEMPLATES[key]
    if allow_adhoc_profile:
        return Profile(name=key, security_mode="development")
    raise ValueError(_UNKNOWN_PROFILE.format(name=key))


def write_profile(profile: Profile, path: str | Path) -> Path:
    """Write a profile as JSON through :class:`~etlantic.io_policy.SafeIoPolicy`.

    Args:
        profile: Profile to serialize.
        path: Destination ``.json`` path (parent directories created).

    Returns:
        Resolved absolute output path.

    Raises:
        UnsafeLoadError: When the path violates safe I/O policy (e.g. escape
            outside the parent root, symlink, overwrite rejection).
        OSError: When the file cannot be written.
    """
    from etlantic.io_policy import SafeIoPolicy, write_text_safe

    resolved = Path(path).expanduser()
    parent = resolved.parent
    parent.mkdir(parents=True, exist_ok=True)
    policy = SafeIoPolicy.for_root(parent)
    text = json.dumps(profile.to_dict(), indent=2, sort_keys=True) + "\n"
    write_text_safe(resolved, text, policy, run_id="profile-write")
    return resolved.resolve()


def load_profile(
    path: str | Path,
    *,
    accept_legacy_bindings: bool = False,
) -> Profile:
    """Load a profile from a JSON file.

    Args:
        path: Profile JSON document.
        accept_legacy_bindings: Forwarded to :meth:`Profile.from_dict` for
            legacy ``bindings`` keys (default fail-closed ``PMCFG111``).

    Returns:
        Parsed :class:`Profile` (legacy ``bindings`` keys may warn ``PMCFG110``).

    Raises:
        ValueError: When the document is not a JSON object or fields are invalid.
        OSError: When the file cannot be read.
        UnsafeLoadError: When the path escapes the profile directory root.
        json.JSONDecodeError: When the file is not valid JSON.
    """
    from etlantic.io_policy import SafeIoPolicy, read_text_safe

    resolved = Path(path).expanduser()
    parent = resolved.parent
    policy = SafeIoPolicy.for_root(parent)
    _resolved, text, _events = read_text_safe(resolved, policy, run_id="profile-read")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Profile document must be a JSON object")
    return Profile.from_dict(data, accept_legacy_bindings=accept_legacy_bindings)
