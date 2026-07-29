"""Asset descriptor parsing for declarative profile bindings."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class ParsedAssetDescriptor:
    """Normalized asset provider and optional location."""

    provider: str
    location: str | None = None
    metadata: dict[str, Any] | None = None


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
        return cls(
            name=str(data["name"]),
            provider=str(data.get("provider") or "memory"),
            location=(str(data["location"]) if data.get("location") is not None else None),
            catalog=(str(data["catalog"]) if data.get("catalog") is not None else None),
            namespace=(
                str(data["namespace"]) if data.get("namespace") is not None else None
            ),
            table=(str(data["table"]) if data.get("table") is not None else None),
            format=(str(data["format"]) if data.get("format") is not None else None),
            jdbc_driver=(
                str(data["jdbc_driver"]) if data.get("jdbc_driver") is not None else None
            ),
            secret_refs={
                str(k): str(v) for k, v in dict(data.get("secret_refs") or {}).items()
            },
            options={str(k): str(v) for k, v in dict(data.get("options") or {}).items()},
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
        fmt = None
        jdbc_driver = None
        if provider in {"jdbc", "spark_jdbc"}:
            fmt = "jdbc"
        return cls(
            name=name,
            provider=provider,
            location=parsed.location,
            catalog=catalog,
            namespace=namespace,
            table=table,
            format=fmt,
            jdbc_driver=jdbc_driver,
            secret_refs=dict(secret_refs or {}),
            options=dict(options or {}),
            cross_schema=cross_schema,
        )


_METADATA_UNSUPPORTED = (
    "Asset descriptor metadata is not persisted in 0.21; "
    "omit metadata or use provider://location string form."
)


def asset_descriptor_to_storage_key(value: str | dict[str, Any]) -> str:
    """Normalize an asset descriptor to a string stored in Profile.bindings."""
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        raise ValueError(
            f"Asset descriptor must be str or mapping, got {type(value)!r}"
        )
    metadata = value.get("metadata")
    if isinstance(metadata, dict) and metadata:
        raise ValueError(_METADATA_UNSUPPORTED)
    provider = str(value.get("provider") or value.get("binding") or "").strip()
    if not provider:
        raise ValueError("Asset descriptor object requires 'provider'")
    location = value.get("location")
    if location is None:
        return provider
    return f"{provider}://{location}"


def parse_asset_descriptor(value: str | dict[str, Any]) -> ParsedAssetDescriptor:
    """Parse a profile asset value into provider and location."""
    if isinstance(value, dict):
        metadata_raw = value.get("metadata")
        metadata = dict(metadata_raw) if isinstance(metadata_raw, dict) else None
        if metadata:
            raise ValueError(_METADATA_UNSUPPORTED)
        provider = str(value.get("provider") or value.get("binding") or "").strip()
        if not provider:
            raise ValueError("Asset descriptor object requires 'provider'")
        location = value.get("location")
        return ParsedAssetDescriptor(
            provider=provider,
            location=str(location) if location is not None else None,
            metadata=None,
        )

    text = str(value).strip()
    if "://" in text:
        parsed = urlparse(text)
        provider = parsed.scheme or "memory"
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


def normalize_assets_map(raw: dict[str, Any]) -> dict[str, str]:
    """Normalize profile assets from JSON into string storage form."""
    normalized: dict[str, str] = {}
    for key, value in dict(raw or {}).items():
        if isinstance(value, str):
            normalized[str(key)] = value
        elif isinstance(value, dict):
            normalized[str(key)] = asset_descriptor_to_storage_key(value)
        else:
            raise ValueError(
                f"Asset {key!r} must be a string or descriptor object, "
                f"got {type(value)!r}"
            )
    return normalized
