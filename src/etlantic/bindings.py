"""Asset descriptor parsing for declarative profile bindings."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

_USERINFO_REJECT = (
    "Asset URL must not include userinfo credentials "
    "(user:password@host); use SecretRef / secret_refs for auth"
)

# Structured connector descriptor keys (ADR-015 / 038-B01).
_CONNECTOR_STRUCTURED_KEYS = frozenset(
    {
        "format",
        "config",
        "mode",
        "glob",
        "root",
        "root_ref",
        "consume",
        "checkpoint",
        "required_capabilities",
        "secret_refs",
        "protocol",
        "provider_version",
        "empty_match",
    }
)

_METADATA_UNSUPPORTED = (
    "Asset descriptor metadata is not persisted as an opaque bag; "
    "use structured connector fields (format, config, mode, …) instead."
)

AssetValue = str | dict[str, Any]


def _reject_location_userinfo(location: str | None) -> None:
    """Fail closed when a location embeds URL userinfo credentials."""
    if location is None:
        return
    text = str(location).strip()
    if not text:
        return
    # Full URL or scheme-relative / host-with-userinfo forms.
    candidates = [text]
    if "://" not in text and "@" in text:
        candidates.append(f"scheme://{text}")
    for candidate in candidates:
        parsed = urlparse(candidate if "://" in candidate else f"scheme://{candidate}")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError(_USERINFO_REJECT)
        # urlparse may put user:pass@host in path for odd shapes — check raw.
        if "@" in text and "://" in text:
            before_at = text.split("@", 1)[0]
            if "://" in before_at and ":" in before_at.rsplit("://", 1)[-1]:
                raise ValueError(_USERINFO_REJECT)


@dataclass(frozen=True, slots=True)
class ParsedAssetDescriptor:
    """Normalized asset provider and optional location / connector fields."""

    provider: str
    location: str | None = None
    metadata: dict[str, Any] | None = None
    format: str | None = None
    config: dict[str, Any] | None = None
    mode: str | None = None
    glob: str | None = None
    root: str | None = None
    root_ref: str | None = None
    consume: str | None = None
    checkpoint: str | None = None
    required_capabilities: tuple[str, ...] = ()
    secret_refs: dict[str, str] | None = None
    protocol: str | None = None
    provider_version: str | None = None
    empty_match: str | None = None

    @property
    def is_structured_connector(self) -> bool:
        return bool(
            self.format
            or self.config
            or self.mode
            or self.glob
            or self.root
            or self.root_ref
            or self.consume
            or self.checkpoint
            or self.required_capabilities
            or self.protocol
            or self.provider_version
            or self.empty_match
        )

    def to_canonical(self) -> AssetValue:
        """Return legacy string form or canonical structured connector dict."""
        if not self.is_structured_connector:
            if self.location is None:
                return self.provider
            return f"{self.provider}://{self.location}"
        data: dict[str, Any] = {"provider": self.provider}
        if self.location is not None:
            data["location"] = self.location
        if self.format is not None:
            data["format"] = self.format
        if self.config:
            data["config"] = dict(self.config)
        if self.mode is not None:
            data["mode"] = self.mode
        if self.glob is not None:
            data["glob"] = self.glob
        if self.root is not None:
            data["root"] = self.root
        if self.root_ref is not None:
            data["root_ref"] = self.root_ref
        if self.consume is not None:
            data["consume"] = self.consume
        if self.checkpoint is not None:
            data["checkpoint"] = self.checkpoint
        if self.required_capabilities:
            data["required_capabilities"] = list(self.required_capabilities)
        if self.secret_refs:
            data["secret_refs"] = dict(self.secret_refs)
        if self.protocol is not None:
            data["protocol"] = self.protocol
        if self.provider_version is not None:
            data["provider_version"] = self.provider_version
        if self.empty_match is not None:
            data["empty_match"] = self.empty_match
        return data

    def connector_metadata(self) -> dict[str, Any]:
        """Secret-free metadata bag for BindingDescriptor.metadata."""
        meta: dict[str, Any] = {}
        if self.config:
            meta["config"] = dict(self.config)
        if self.glob is not None:
            meta["glob"] = self.glob
        if self.root is not None:
            meta["root"] = self.root
        if self.consume is not None:
            meta["consume"] = self.consume
        if self.checkpoint is not None:
            meta["checkpoint"] = self.checkpoint
        if self.empty_match is not None:
            meta["empty_match"] = self.empty_match
        if self.secret_refs:
            meta["secret_refs"] = dict(self.secret_refs)
        return meta


@dataclass(frozen=True, slots=True)
class AssetBindingRef:
    """Plugin-facing asset / JDBC binding without credentials.

    Use ``secret_refs`` for credential lookup at acquire time. Never embed
    passwords, tokens, or connection URLs with userinfo in plans or reports.
    """

    name: str
    provider: str
    location: str | None = None
    catalog: str | None = None
    namespace: str | None = None
    table: str | None = None
    format: str | None = None
    jdbc_driver: str | None = None
    secret_refs: Mapping[str, str] = field(default_factory=dict)
    options: Mapping[str, str] = field(default_factory=dict)
    cross_schema: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "provider": self.provider,
            "location": self.location,
            "catalog": self.catalog,
            "namespace": self.namespace,
            "table": self.table,
            "format": self.format,
            "jdbc_driver": self.jdbc_driver,
            "secret_refs": dict(self.secret_refs),
            "options": dict(self.options),
            "cross_schema": self.cross_schema,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AssetBindingRef:
        location = str(data["location"]) if data.get("location") is not None else None
        _reject_location_userinfo(location)
        return cls(
            name=str(data["name"]),
            provider=str(data.get("provider") or "memory"),
            location=location,
            catalog=(str(data["catalog"]) if data.get("catalog") is not None else None),
            namespace=(
                str(data["namespace"]) if data.get("namespace") is not None else None
            ),
            table=(str(data["table"]) if data.get("table") is not None else None),
            format=(str(data["format"]) if data.get("format") is not None else None),
            jdbc_driver=(
                str(data["jdbc_driver"])
                if data.get("jdbc_driver") is not None
                else None
            ),
            secret_refs={
                str(k): str(v) for k, v in dict(data.get("secret_refs") or {}).items()
            },
            options={
                str(k): str(v) for k, v in dict(data.get("options") or {}).items()
            },
            cross_schema=bool(data.get("cross_schema", False)),
        )

    @classmethod
    def from_descriptor(
        cls,
        name: str,
        descriptor: str | dict[str, Any] | ParsedAssetDescriptor,
        *,
        catalog: str | None = None,
        namespace: str | None = None,
        table: str | None = None,
        secret_refs: Mapping[str, str] | None = None,
        options: Mapping[str, str] | None = None,
        cross_schema: bool = False,
    ) -> AssetBindingRef:
        """Build a binding ref from a profile asset descriptor."""
        if isinstance(descriptor, ParsedAssetDescriptor):
            parsed = descriptor
        else:
            parsed = parse_asset_descriptor(descriptor)
        provider = parsed.provider
        fmt = parsed.format
        jdbc_driver = None
        if provider in {"jdbc", "spark_jdbc"}:
            fmt = "jdbc"
        refs = dict(secret_refs or {})
        if parsed.secret_refs:
            refs = {**dict(parsed.secret_refs), **refs}
        return cls(
            name=name,
            provider=provider,
            location=parsed.location,
            catalog=catalog,
            namespace=namespace,
            table=table,
            format=fmt,
            jdbc_driver=jdbc_driver,
            secret_refs=refs,
            options=dict(options or {}),
            cross_schema=cross_schema,
        )


def asset_descriptor_to_storage_key(value: str | dict[str, Any]) -> AssetValue:
    """Normalize an asset descriptor to profile storage form.

    Legacy provider/location-only descriptors remain strings. Structured
    connector descriptors are stored as canonical dicts.
    """
    parsed = parse_asset_descriptor(value)
    return parsed.to_canonical()


def parse_asset_descriptor(value: str | dict[str, Any]) -> ParsedAssetDescriptor:
    """Parse a profile asset value into provider, location, and connector fields."""
    if isinstance(value, dict):
        metadata_raw = value.get("metadata")
        if isinstance(metadata_raw, dict) and metadata_raw:
            # Reject opaque metadata bags; connector fields are first-class.
            unknown_meta = set(metadata_raw) - _CONNECTOR_STRUCTURED_KEYS
            if unknown_meta:
                raise ValueError(_METADATA_UNSUPPORTED)
        provider = str(value.get("provider") or value.get("binding") or "").strip()
        if not provider:
            raise ValueError("Asset descriptor object requires 'provider'")
        location = value.get("location")
        location_text = str(location) if location is not None else None
        _reject_location_userinfo(location_text)
        config_raw = value.get("config")
        config = dict(config_raw) if isinstance(config_raw, dict) else None
        if config is not None:
            # Lazy import: avoid connectors package during Profile bootstrap.
            from etlantic.connectors.cdk.config import reject_secret_like_keys

            # Fail closed before planner/profile snapshots can embed secrets.
            reject_secret_like_keys(config, path="config", provider=provider)
        caps_raw = value.get("required_capabilities") or ()
        secret_refs_raw = value.get("secret_refs") or {}
        return ParsedAssetDescriptor(
            provider=provider,
            location=location_text,
            metadata=None,
            format=(str(value["format"]) if value.get("format") is not None else None),
            config=config,
            mode=(str(value["mode"]) if value.get("mode") is not None else None),
            glob=(str(value["glob"]) if value.get("glob") is not None else None),
            root=(str(value["root"]) if value.get("root") is not None else None),
            root_ref=(
                str(value["root_ref"]) if value.get("root_ref") is not None else None
            ),
            consume=(
                str(value["consume"]) if value.get("consume") is not None else None
            ),
            checkpoint=(
                str(value["checkpoint"])
                if value.get("checkpoint") is not None
                else None
            ),
            required_capabilities=tuple(str(x) for x in caps_raw),
            secret_refs=(
                {str(k): str(v) for k, v in dict(secret_refs_raw).items()}
                if secret_refs_raw
                else None
            ),
            protocol=(
                str(value["protocol"]) if value.get("protocol") is not None else None
            ),
            provider_version=(
                str(value["provider_version"])
                if value.get("provider_version") is not None
                else None
            ),
            empty_match=(
                str(value["empty_match"])
                if value.get("empty_match") is not None
                else None
            ),
        )

    text = str(value).strip()
    if "://" in text:
        parsed = urlparse(text)
        provider = parsed.scheme or "memory"
        # Plans must stay secret-free: never embed URL userinfo (user:password@).
        if parsed.username is not None or parsed.password is not None:
            raise ValueError(_USERINFO_REJECT)
        if parsed.netloc:
            # file://localhost/tmp/x → treat as absolute /tmp/x
            if provider == "file" and parsed.netloc in {"localhost", "127.0.0.1"}:
                location = parsed.path or None
            else:
                location = f"{parsed.netloc}{parsed.path}"
        else:
            # Preserve absolute paths (json:///tmp/x → /tmp/x).
            location = parsed.path or None
        return ParsedAssetDescriptor(provider=provider, location=location or None)
    return ParsedAssetDescriptor(provider=text or "memory", location=None)


def normalize_assets_map(raw: dict[str, Any]) -> dict[str, AssetValue]:
    """Normalize profile assets from JSON into canonical storage form.

    Every value is validated through :func:`parse_asset_descriptor` so credential
    URLs cannot enter profiles or plan snapshots. Structured connector
    descriptors retain canonical dict form; legacy forms remain strings.
    """
    normalized: dict[str, AssetValue] = {}
    for key, value in dict(raw or {}).items():
        if isinstance(value, (str, dict)):
            normalized[str(key)] = asset_descriptor_to_storage_key(value)
        else:
            raise ValueError(
                f"Asset {key!r} must be a string or descriptor object, "
                f"got {type(value)!r}"
            )
    return normalized
