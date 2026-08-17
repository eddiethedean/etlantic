"""Plan-time connector capability negotiation (fail closed)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

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
            "idempotency",
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


def _lookup_connector_capabilities(
    *,
    provider: str,
    kind: str,
    runtime_connectors: Mapping[str, Any] | None = None,
) -> frozenset[str] | None:
    """Resolve advertised capabilities for a known provider when possible."""
    registry = runtime_connectors or {}
    connector = registry.get(provider)
    if connector is not None and hasattr(connector, "info"):
        try:
            info = connector.info()
            caps = getattr(info, "capabilities", ()) or ()
            return frozenset(str(c) for c in caps)
        except Exception:
            pass

    if provider == "local-files" and kind == "source":
        try:
            from etlantic.connectors.local_files import create_local_files_source

            return frozenset(create_local_files_source().info().capabilities)
        except Exception:
            return LOCAL_FILES_CAPABILITIES

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
    }
    target = import_map.get((provider, kind))
    if target is not None:
        module_name, attr = target
        try:
            import importlib

            mod = importlib.import_module(module_name)
            factory = getattr(mod, attr)
            return frozenset(factory().info().capabilities)
        except Exception:
            pass

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
        available = _lookup_connector_capabilities(
            provider=provider,
            kind=kind,
            runtime_connectors=runtime,
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
    "assert_binding_connector_capabilities",
]
