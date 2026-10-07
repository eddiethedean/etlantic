"""Secret-safe catalog of connector schemas allowed by an execution profile."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, cast

from etlantic._version import __version__
from etlantic.connectors.discovery import (
    SINK_CONNECTORS_GROUP,
    SOURCE_CONNECTORS_GROUP,
    STORAGE_CONNECTORS_GROUP,
    connector_key,
    discover_connectors_for_profile,
)
from etlantic.connectors.local_files import create_local_files_source
from etlantic.plugin_lifecycle import PluginLifecycleResult
from etlantic.profile import Profile

CONNECTOR_CATALOG_SCHEMA = "etlantic.connector_catalog/1"
_SENSITIVE_SAMPLE_FIELDS = {"default", "example", "examples", "const", "enum"}
_SENSITIVE_OPTION = re.compile(
    r"(?:secret|password|passwd|token|credential|authorization|api[_-]?key|"
    r"private[_-]?key|access[_-]?key|signing[_-]?key|connection[_-]?string|dsn)",
    re.IGNORECASE,
)
_GROUP_KIND = {
    SOURCE_CONNECTORS_GROUP: "source",
    SINK_CONNECTORS_GROUP: "sink",
    STORAGE_CONNECTORS_GROUP: "storage",
}


def _is_sensitive_option(name: str) -> bool:
    """Recognize common credential field names across casing conventions."""
    normalized_name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    return bool(_SENSITIVE_OPTION.search(normalized_name)) or (
        normalized_name.lower() == "key"
    )


def _redact_sensitive_sample(value: Any) -> Any:
    """Remove credential-named members from nested provider sample values."""
    if isinstance(value, Mapping):
        sample = cast(Mapping[str, Any], value)
        return {
            str(key): _redact_sensitive_sample(child)
            for key, child in sample.items()
            if not _is_sensitive_option(str(key))
        }
    if isinstance(value, list):
        return [_redact_sensitive_sample(child) for child in cast(list[Any], value)]
    if isinstance(value, tuple):
        return [
            _redact_sensitive_sample(child) for child in cast(tuple[Any, ...], value)
        ]
    return value


def _schema_without_sensitive_defaults(value: Any, *, sensitive: bool = False) -> Any:
    """Copy a provider schema while removing defaults for secret-like fields."""
    if isinstance(value, Mapping):
        raw = dict(cast(Mapping[str, Any], value))
        marked_sensitive = sensitive or any(
            raw.get(key) is True for key in ("writeOnly", "x-sensitive", "sensitive")
        )
        result: dict[str, Any] = {}
        for key, child in raw.items():
            if key in _SENSITIVE_SAMPLE_FIELDS:
                if marked_sensitive:
                    continue
                result[key] = _redact_sensitive_sample(child)
                continue
            if key == "properties" and isinstance(child, Mapping):
                property_schemas = cast(Mapping[str, Any], child)
                properties: dict[str, Any] = {}
                for name, field_schema in property_schemas.items():
                    field_is_sensitive = marked_sensitive or _is_sensitive_option(
                        str(name)
                    )
                    sanitized = _schema_without_sensitive_defaults(
                        field_schema,
                        sensitive=field_is_sensitive,
                    )
                    if (
                        field_is_sensitive
                        and isinstance(sanitized, dict)
                        and "x-sensitive" not in sanitized
                    ):
                        sanitized["x-sensitive"] = True
                    properties[str(name)] = sanitized
                result[str(key)] = properties
            else:
                result[str(key)] = _schema_without_sensitive_defaults(
                    child, sensitive=marked_sensitive
                )
        return result
    if isinstance(value, list):
        return [
            _schema_without_sensitive_defaults(child, sensitive=sensitive)
            for child in cast(list[Any], value)
        ]
    if isinstance(value, tuple):
        return [
            _schema_without_sensitive_defaults(child, sensitive=sensitive)
            for child in cast(tuple[Any, ...], value)
        ]
    return value


def _diagnostic_summary(result: PluginLifecycleResult) -> list[dict[str, Any]]:
    """Expose stable plugin diagnostics without provider-controlled messages."""
    return [
        {
            "code": item.code,
            "severity": item.severity.value,
            "phase": item.phase,
            "path": list(item.path),
        }
        for item in sorted(
            result.diagnostics,
            key=lambda diagnostic: (
                diagnostic.code,
                diagnostic.phase,
                tuple(str(part) for part in diagnostic.path),
            ),
        )
    ]


def connector_catalog_for_profile(profile: Profile) -> dict[str, Any]:
    """Discover authorized connector packages and publish their option schemas.

    The profile's plugin trust policy is applied before a provider factory is
    loaded. The catalog contains only protocol metadata and JSON Schemas; it
    never returns connector instances, bindings, or configuration values.
    """
    results = discover_connectors_for_profile(profile, run_id="connector-catalog")
    entries: list[dict[str, Any]] = []

    for group, kind in _GROUP_KIND.items():
        result = results.get(group, PluginLifecycleResult())
        discovered = {item.name: item for item in result.authorized}
        for key, connector in sorted(result.loaded.items()):
            try:
                info = connector.info()
                raw_schema = getattr(info, "configuration_schema", None)
                schema_copy: dict[str, Any] | None = None
                if isinstance(raw_schema, Mapping):
                    sanitized_schema = _schema_without_sensitive_defaults(
                        cast(Mapping[str, Any], raw_schema)
                    )
                    if isinstance(sanitized_schema, dict):
                        schema_copy = cast(dict[str, Any], sanitized_schema)
                plugin = next(
                    (
                        item
                        for item in result.authorized
                        if connector_key(item, connector) == key
                    ),
                    discovered.get(key),
                )
                entries.append(
                    {
                        "name": str(getattr(info, "name", key)),
                        "kind": kind,
                        "provider": (
                            str(info.provider)
                            if getattr(info, "provider", None) is not None
                            else None
                        ),
                        "protocol": str(getattr(info, "protocol", "")),
                        "version": str(getattr(info, "version", "0.0.0")),
                        "package": (
                            plugin.distribution_name if plugin is not None else None
                        ),
                        "package_version": (
                            plugin.distribution_version if plugin is not None else None
                        ),
                        "capabilities": sorted(
                            str(capability)
                            for capability in (getattr(info, "capabilities", ()) or ())
                        ),
                        "maturity": str(
                            getattr(
                                getattr(info, "maturity", None), "value", "experimental"
                            )
                        ),
                        "configuration_schema": schema_copy,
                        "schema_available": bool(schema_copy),
                    }
                )
            except Exception:
                # A broken provider is listed as unavailable without leaking
                # exception text or configuration values through discovery.
                entries.append(
                    {
                        "name": str(key),
                        "kind": kind,
                        "provider": str(key),
                        "protocol": None,
                        "version": None,
                        "package": None,
                        "package_version": None,
                        "capabilities": [],
                        "maturity": "experimental",
                        "configuration_schema": None,
                        "schema_available": False,
                        "unavailable_reason": "provider_metadata_error",
                    }
                )

    # The in-tree source is deliberately exempt from entry-point allowlists,
    # matching PipelineRuntime's local-files registration behavior.
    if not any(
        entry["kind"] == "source" and entry["name"] == "local-files"
        for entry in entries
    ):
        info = create_local_files_source().info()
        schema = cast(
            dict[str, Any],
            _schema_without_sensitive_defaults(info.configuration_schema),
        )
        entries.append(
            {
                "name": info.name,
                "kind": "source",
                "provider": info.provider,
                "protocol": info.protocol,
                "version": info.version,
                "package": "etlantic",
                "package_version": __version__,
                "capabilities": sorted(info.capabilities),
                "maturity": info.maturity.value,
                "configuration_schema": schema,
                "schema_available": bool(schema),
            }
        )

    entries.sort(key=lambda entry: (str(entry["kind"]), str(entry["name"])))
    return {
        "schema": CONNECTOR_CATALOG_SCHEMA,
        "etlantic_version": __version__,
        "profile": profile.name,
        "connectors": entries,
        "diagnostics": [
            diagnostic
            for group in _GROUP_KIND
            for diagnostic in _diagnostic_summary(
                results.get(group, PluginLifecycleResult())
            )
        ],
    }


__all__ = ["CONNECTOR_CATALOG_SCHEMA", "connector_catalog_for_profile"]
