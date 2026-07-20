"""Asset descriptor parsing for declarative profile bindings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class ParsedAssetDescriptor:
    """Normalized asset provider and optional location."""

    provider: str
    location: str | None = None
    metadata: dict[str, Any] | None = None


def asset_descriptor_to_storage_key(value: str | dict[str, Any]) -> str:
    """Normalize an asset descriptor to a string stored in Profile.bindings."""
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        raise ValueError(
            f"Asset descriptor must be str or mapping, got {type(value)!r}"
        )
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
        provider = str(value.get("provider") or value.get("binding") or "").strip()
        if not provider:
            raise ValueError("Asset descriptor object requires 'provider'")
        location = value.get("location")
        metadata_raw = value.get("metadata")
        metadata = dict(metadata_raw) if isinstance(metadata_raw, dict) else None
        return ParsedAssetDescriptor(
            provider=provider,
            location=str(location) if location is not None else None,
            metadata=metadata,
        )

    text = str(value).strip()
    if "://" in text:
        parsed = urlparse(text)
        provider = parsed.scheme or "memory"
        location = parsed.path
        if parsed.netloc:
            location = f"{parsed.netloc}{parsed.path}"
        if location.startswith("/") and provider in {"json", "csv", "file"}:
            location = location.lstrip("/")
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
