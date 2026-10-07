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


def _local_schema(root: Mapping[str, Any], reference: str) -> Mapping[str, Any] | None:
    """Resolve a local JSON Schema pointer, failing closed for other references."""
    if not reference.startswith("#/"):
        return None
    current: Any = root
    try:
        for part in reference[2:].split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            current = current[part]
    except (KeyError, TypeError):
        return None
    return cast(Mapping[str, Any], current) if isinstance(current, Mapping) else None


def _schema_parts(
    schema: Mapping[str, Any],
    root: Mapping[str, Any],
    seen: frozenset[str] = frozenset(),
) -> tuple[list[Mapping[str, Any]], bool]:
    """Return a schema and its local ref/composition targets; flag unresolved refs."""
    parts = [schema]
    # Dynamic/recursive scope depends on the containing schema walk. Until it is
    # resolved explicitly, samples described by these references are unsafe.
    failed = "$dynamicRef" in schema or "$recursiveRef" in schema
    reference = schema.get("$ref")
    if isinstance(reference, str):
        if reference in seen:
            failed = True
        else:
            target = _local_schema(root, reference)
            if target is None:
                failed = True
            else:
                nested, nested_failed = _schema_parts(target, root, seen | {reference})
                parts.extend(nested)
                failed |= nested_failed
    elif "$ref" in schema:
        failed = True
    for keyword in ("allOf", "anyOf", "oneOf", "if", "then", "else"):
        children = schema.get(keyword)
        if isinstance(children, Mapping):
            nested, nested_failed = _schema_parts(children, root, seen)
            parts.extend(nested)
            failed |= nested_failed
        elif isinstance(children, list):
            for child in children:
                if isinstance(child, Mapping):
                    nested, nested_failed = _schema_parts(child, root, seen)
                    parts.extend(nested)
                    failed |= nested_failed
    dependent_schemas = schema.get("dependentSchemas")
    if isinstance(dependent_schemas, Mapping):
        for child in dependent_schemas.values():
            if isinstance(child, Mapping):
                nested, nested_failed = _schema_parts(child, root, seen)
                parts.extend(nested)
                failed |= nested_failed
    return parts, failed


def _is_schema_sensitive(schema: Mapping[str, Any], root: Mapping[str, Any]) -> bool:
    parts, failed = _schema_parts(schema, root)
    return failed or any(
        any(
            part.get(marker) is True
            for marker in ("writeOnly", "x-sensitive", "sensitive")
        )
        for part in parts
    )


def _child_schemas(
    schemas: list[Mapping[str, Any]], root: Mapping[str, Any], name: str
) -> list[Mapping[str, Any]]:
    children: list[Mapping[str, Any]] = []
    for schema in schemas:
        parts, _ = _schema_parts(schema, root)
        for part in parts:
            matched = False
            properties = part.get("properties")
            if isinstance(properties, Mapping) and isinstance(
                properties.get(name), Mapping
            ):
                children.append(cast(Mapping[str, Any], properties[name]))
                matched = True
            pattern_properties = part.get("patternProperties")
            if isinstance(pattern_properties, Mapping):
                for pattern, child in pattern_properties.items():
                    if (
                        isinstance(pattern, str)
                        and re.search(pattern, name)
                        and isinstance(child, Mapping)
                    ):
                        children.append(cast(Mapping[str, Any], child))
                        matched = True
            additional = part.get("additionalProperties")
            if not matched and isinstance(additional, Mapping):
                children.append(cast(Mapping[str, Any], additional))
                matched = True
            unevaluated = part.get("unevaluatedProperties")
            if not matched and isinstance(unevaluated, Mapping):
                children.append(cast(Mapping[str, Any], unevaluated))
    return children


def _item_schemas(
    schemas: list[Mapping[str, Any]], root: Mapping[str, Any], index: int
) -> list[Mapping[str, Any]]:
    children: list[Mapping[str, Any]] = []
    for schema in schemas:
        parts, _ = _schema_parts(schema, root)
        for part in parts:
            matched = False
            contains = part.get("contains")
            if isinstance(contains, Mapping):
                # The array item's match cannot be established without full
                # validation, so conservatively apply its sensitivity schema.
                children.append(cast(Mapping[str, Any], contains))
            prefix_items = part.get("prefixItems")
            if isinstance(prefix_items, list) and index < len(prefix_items):
                item = prefix_items[index]
                if isinstance(item, Mapping):
                    children.append(cast(Mapping[str, Any], item))
                matched = True
                continue
            items = part.get("items")
            if isinstance(items, Mapping):
                children.append(cast(Mapping[str, Any], items))
                matched = True
            elif isinstance(items, list) and index < len(items):
                if isinstance(items[index], Mapping):
                    children.append(cast(Mapping[str, Any], items[index]))
                matched = True
            unevaluated = part.get("unevaluatedItems")
            if not matched and isinstance(unevaluated, Mapping):
                children.append(cast(Mapping[str, Any], unevaluated))
    return children


def _sanitize_sample(
    value: Any,
    schemas: list[Mapping[str, Any]],
    root: Mapping[str, Any],
    *,
    seen: frozenset[int] = frozenset(),
) -> tuple[Any, bool]:
    """Sanitize one sample using its schema context; bool is false if unsafe."""
    if any(_is_schema_sensitive(schema, root) for schema in schemas):
        return None, False
    if isinstance(value, Mapping):
        if id(value) in seen:
            return None, False
        visited = seen | {id(value)}
        sample: dict[str, Any] = {}
        for raw_name, child in value.items():
            name = str(raw_name)
            child_schemas = _child_schemas(schemas, root, name)
            if _is_sensitive_option(name) or any(
                _is_schema_sensitive(child_schema, root)
                for child_schema in child_schemas
            ):
                continue
            sanitized, safe = _sanitize_sample(child, child_schemas, root, seen=visited)
            if safe:
                sample[name] = sanitized
        return sample, True
    if isinstance(value, (list, tuple)):
        if id(value) in seen:
            return None, False
        visited = seen | {id(value)}
        sample: list[Any] = []
        for index, child in enumerate(value):
            item_schemas = _item_schemas(schemas, root, index)
            sanitized, safe = _sanitize_sample(child, item_schemas, root, seen=visited)
            if not safe:
                return None, False
            sample.append(sanitized)
        return sample, True
    return value, True


def _schema_without_sensitive_defaults(
    value: Any, *, sensitive: bool = False, root: Mapping[str, Any] | None = None
) -> Any:
    """Copy a provider schema while removing schema-sensitive sample values."""
    if root is None and isinstance(value, Mapping):
        root = cast(Mapping[str, Any], value)
    root = root or {}
    if isinstance(value, Mapping):
        raw = dict(cast(Mapping[str, Any], value))
        marked_sensitive = sensitive or _is_schema_sensitive(raw, root)
        result: dict[str, Any] = {}
        for key, child in raw.items():
            if key in _SENSITIVE_SAMPLE_FIELDS:
                if marked_sensitive:
                    continue
                if key in {"examples", "enum"} and isinstance(child, (list, tuple)):
                    sanitized_values = []
                    for sample in child:
                        sanitized, safe = _sanitize_sample(sample, [raw], root)
                        if safe:
                            sanitized_values.append(sanitized)
                    result[key] = sanitized_values
                else:
                    sanitized, safe = _sanitize_sample(child, [raw], root)
                    if safe:
                        result[key] = sanitized
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
                        root=root,
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
                    child, sensitive=marked_sensitive, root=root
                )
        return result
    if isinstance(value, list):
        return [
            _schema_without_sensitive_defaults(child, sensitive=sensitive, root=root)
            for child in cast(list[Any], value)
        ]
    if isinstance(value, tuple):
        return [
            _schema_without_sensitive_defaults(child, sensitive=sensitive, root=root)
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
