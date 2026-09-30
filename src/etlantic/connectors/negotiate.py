"""Plan-time connector capability negotiation (fail closed)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from etlantic.connectors.capabilities import (
    LOCAL_FILES_CAPABILITIES,
    SOURCE_BATCH_SNAPSHOT,
    SOURCE_FILE_GLOB,
    SOURCE_INCREMENTAL_CURSOR,
    SOURCE_STREAM,
    SOURCE_WATERMARK,
    WRITE_APPEND,
    WRITE_MERGE,
    WRITE_OVERWRITE,
    WRITE_PARTITION_REPLACE,
)
from etlantic.diagnostics import Diagnostic, Severity, ValidationReport
from etlantic.exceptions import PipelineValidationError
from etlantic.registry import BindingDescriptor

# Stable diagnostic for unsupported connector mode/capability at plan time.
PMCONN850 = "PMCONN850"
# Stable diagnostic for options that do not match an installed provider schema.
PMCONN880 = "PMCONN880"

# First-party / builtin capability maps used when packages are not imported yet.
_KNOWN_SOURCE_CAPS: dict[str, frozenset[str]] = {
    "local-files": LOCAL_FILES_CAPABILITIES,
    "s3": frozenset(
        {
            "source.batch_snapshot",
            "source.schema_discovery",
            "source.statistics_bounded",
            "idempotency",
        }
    ),
    "iceberg": frozenset(
        {
            "source.batch_snapshot",
            "source.partitioned",
            "source.schema_discovery",
            "idempotency",
        }
    ),
    "snowflake": frozenset(
        {
            "source.batch_snapshot",
            "source.schema_discovery",
            "source.statistics_bounded",
            "idempotency",
        }
    ),
    "postgresql": frozenset(
        {
            "source.batch_snapshot",
            "source.schema_discovery",
            "source.statistics_bounded",
        }
    ),
    "kafka": frozenset(
        {
            SOURCE_STREAM,
            SOURCE_WATERMARK,
            "idempotency",
        }
    ),
}

_KNOWN_SINK_CAPS: dict[str, frozenset[str]] = {
    "s3": frozenset(
        {
            "write.append",
            "write.overwrite",
            "publication.atomic",
            "reconciliation",
            "cleanup",
            "idempotency",
        }
    ),
    "iceberg": frozenset(
        {
            "write.append",
            "write.overwrite",
            "publication.atomic",
            "reconciliation",
            "idempotency",
        }
    ),
    "snowflake": frozenset(
        {
            "write.append",
            "write.overwrite",
            "write.merge",
            "publication.atomic",
            "transactions",
            "reconciliation",
            "idempotency",
        }
    ),
    "postgresql": frozenset(
        {
            "write.append",
            "write.overwrite",
            "write.merge",
            "publication.atomic",
            "transactions",
            "reconciliation",
            "idempotency",
        }
    ),
    "kafka": frozenset(
        {
            "sink.stream",
            "sink.exactly_once",
            "transactions",
            "publication.atomic",
            "idempotency",
        }
    ),
}

_MODE_TO_SOURCE_CAP: dict[str, str] = {
    "snapshot": SOURCE_BATCH_SNAPSHOT,
    "batch_snapshot": SOURCE_BATCH_SNAPSHOT,
    "incremental": SOURCE_INCREMENTAL_CURSOR,
    "incremental_cursor": SOURCE_INCREMENTAL_CURSOR,
    "stream": SOURCE_STREAM,
    "streaming": SOURCE_STREAM,
}

_MODE_TO_SINK_CAP: dict[str, str] = {
    "append": WRITE_APPEND,
    "overwrite": WRITE_OVERWRITE,
    "merge": WRITE_MERGE,
    "partition_replace": WRITE_PARTITION_REPLACE,
}


def _mode_implied_capabilities(
    *,
    provider: str,
    kind: str,
    mode: str | None,
    config: Mapping[str, Any] | None,
    required: tuple[str, ...],
) -> set[str]:
    needed: set[str] = set(required)
    mode_norm = (mode or "").strip().lower()
    if kind == "source":
        if mode_norm in _MODE_TO_SOURCE_CAP:
            needed.add(_MODE_TO_SOURCE_CAP[mode_norm])
        cfg = config or {}
        if provider == "local-files" or cfg.get("glob") is not None:
            needed.add(SOURCE_FILE_GLOB)
    elif kind == "sink":
        if mode_norm in _MODE_TO_SINK_CAP:
            needed.add(_MODE_TO_SINK_CAP[mode_norm])
    return needed


def _lookup_connector_info(
    *,
    provider: str,
    kind: str,
    runtime_connectors: Mapping[str, Any] | None = None,
) -> Any | None:
    """Resolve installed connector metadata, including its public config schema."""
    registry = runtime_connectors or {}
    connector = registry.get(provider)
    if connector is not None and hasattr(connector, "info"):
        try:
            return connector.info()
        except Exception:
            pass

    if provider == "local-files" and kind == "source":
        try:
            from etlantic.connectors.local_files import create_local_files_source

            return create_local_files_source().info()
        except Exception:
            return None

    # Prefer live info() from importable first-party packages.
    import_map: dict[tuple[str, str], tuple[str, str]] = {
        ("s3", "source"): ("etlantic_s3", "create_source"),
        ("s3", "sink"): ("etlantic_s3", "create_sink"),
        ("iceberg", "source"): ("etlantic_iceberg", "create_source"),
        ("iceberg", "sink"): ("etlantic_iceberg", "create_sink"),
        ("snowflake", "source"): ("etlantic_snowflake", "create_source"),
        ("snowflake", "sink"): ("etlantic_snowflake", "create_sink"),
        ("postgresql", "source"): ("etlantic_sql.connectors", "create_source"),
        ("postgresql", "sink"): ("etlantic_sql.connectors", "create_sink"),
        ("foundry", "source"): ("etlantic_foundry.connectors", "create_source"),
        ("foundry", "sink"): ("etlantic_foundry.connectors", "create_sink"),
        ("foundry", "storage"): ("etlantic_foundry.connectors", "create_storage"),
    }
    target = import_map.get((provider, kind))
    if target is not None:
        module_name, attr = target
        try:
            import importlib

            mod = importlib.import_module(module_name)
            factory = getattr(mod, attr)
            return factory().info()
        except Exception:
            pass

    return None


def _lookup_connector_capabilities(
    *,
    provider: str,
    kind: str,
    runtime_connectors: Mapping[str, Any] | None = None,
) -> frozenset[str] | None:
    """Resolve advertised capabilities for a known provider when possible."""
    info = _lookup_connector_info(
        provider=provider, kind=kind, runtime_connectors=runtime_connectors
    )
    if info is not None:
        caps = getattr(info, "capabilities", ()) or ()
        return frozenset(str(c) for c in caps)

    # Static fallback for known first-party providers (fail closed without import).
    if kind == "source":
        return _KNOWN_SOURCE_CAPS.get(provider)
    if kind == "sink":
        return _KNOWN_SINK_CAPS.get(provider)
    return None


def assert_binding_connector_capabilities(
    bindings: Mapping[str, BindingDescriptor],
    *,
    runtime_source_connectors: Mapping[str, Any] | None = None,
    runtime_sink_connectors: Mapping[str, Any] | None = None,
) -> None:
    """Fail closed when binding mode/required caps exceed connector capabilities.

    Emits ``PMCONN850`` for each unsupported capability or mode mapping.
    Skips only when the provider is unknown and no capability evidence exists.
    """
    diagnostics: list[Diagnostic] = []
    for node_name, desc in bindings.items():
        provider = str(desc.provider or "")
        kind = str(desc.kind or "source")
        runtime = (
            runtime_source_connectors
            if kind == "source"
            else runtime_sink_connectors
            if kind == "sink"
            else None
        )
        info = _lookup_connector_info(
            provider=provider,
            kind=kind,
            runtime_connectors=runtime,
        )
        available = _lookup_connector_capabilities(
            provider=provider,
            kind=kind,
            runtime_connectors=runtime,
        )
        schema = (
            getattr(info, "configuration_schema", None) if info is not None else None
        )
        if isinstance(schema, Mapping) and schema:
            effective_config = dict(desc.config or {})
            schema_data = cast(Mapping[str, Any], schema)
            schema_properties = schema_data.get("properties")
            if isinstance(schema_properties, Mapping):
                schema_properties = cast(Mapping[str, Any], schema_properties)
                # Binding-level semantic fields remain part of the public schema
                # without forcing callers to duplicate them inside config.
                for field_name in ("mode", "format"):
                    field_value = getattr(desc, field_name, None)
                    if field_value is not None and field_name in schema_properties:
                        effective_config.setdefault(field_name, field_value)
            try:
                from jsonschema import Draft202012Validator

                # jsonschema intentionally has no bundled typing metadata.
                # Keep the untyped boundary local to its public validator API.
                validator = cast(Any, Draft202012Validator)(schema_data)
                schema_errors = sorted(
                    validator.iter_errors(effective_config),
                    key=lambda error: (
                        tuple(str(part) for part in error.absolute_path),
                        str(error.validator),
                    ),
                )
            except Exception:
                # Malformed provider schemas are not trusted as evidence. Treat
                # installed schemas as a provider implementation error instead
                # of silently accepting arbitrary options.
                schema_errors = [None]
            for schema_error in schema_errors:
                error_path = (
                    tuple(str(part) for part in schema_error.absolute_path)
                    if schema_error is not None
                    else ()
                )
                keyword = (
                    str(schema_error.validator)
                    if schema_error is not None and schema_error.validator
                    else "schema"
                )
                display_path = ".".join(("config", *error_path))
                diagnostics.append(
                    Diagnostic(
                        code=PMCONN880,
                        severity=Severity.ERROR,
                        message=(
                            f'Binding "{desc.binding}" provider {provider!r} has '
                            f"an invalid configuration at {display_path} "
                            f"(schema rule {keyword!r})"
                        ),
                        path=("bindings", node_name, "config", *error_path),
                        phase="configuration",
                        metadata={
                            "provider": provider,
                            "schema_rule": keyword,
                        },
                    )
                )
        needed = _mode_implied_capabilities(
            provider=provider,
            kind=kind,
            mode=desc.mode,
            config=desc.config,
            required=tuple(desc.required_capabilities or ()),
        )
        if not needed:
            continue
        if available is None:
            # Unknown provider with no discoverable info — cannot negotiate.
            continue
        missing = sorted(needed - set(available))
        for cap in missing:
            diagnostics.append(
                Diagnostic(
                    code=PMCONN850,
                    severity=Severity.ERROR,
                    message=(
                        f'Binding "{desc.binding}" provider {provider!r} does not '
                        f"support required capability {cap!r}"
                        + (f" (mode={desc.mode!r})" if desc.mode else "")
                    ),
                    path=("bindings", node_name, "capabilities", cap),
                    phase="capability",
                    metadata={
                        "provider": provider,
                        "capability": cap,
                        "mode": desc.mode,
                        "available": sorted(available),
                    },
                )
            )
    if not diagnostics:
        return
    raise PipelineValidationError(
        "Unsupported connector capabilities for one or more bindings.",
        report=ValidationReport.from_diagnostics(diagnostics, phases=("capability",)),
    )


__all__ = [
    "PMCONN850",
    "PMCONN880",
    "assert_binding_connector_capabilities",
]
