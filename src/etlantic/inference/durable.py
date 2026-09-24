# pyright: reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnnecessaryIsInstance=false
"""Row-free, versioned bindings used by inferred pipeline definitions."""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import weakref
from collections.abc import Callable, Mapping
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Any

from etlantic.authoring.definition import NodeDefinition, PipelineDefinition
from etlantic.authoring.serialize import pipeline_fingerprint
from etlantic.plan.freeze import mutable_copy

from .types import InferenceLimits, TargetObservation, _wire_value

BINDING_VERSION = 1

_SOURCE_FACTORIES: dict[str, Callable[[], Any]] = {}
_SOURCE_SCHEMAS: dict[str, tuple[tuple[str, str, bool, bool], ...]] = {}


class _FileSourceEntry:
    __slots__ = ("leases", "path")

    def __init__(self, path: Path) -> None:
        self.path = path
        self.leases: set[weakref.ReferenceType[_FileSourceLease]] = set()


class _FileSourceLease:
    __slots__ = ("__weakref__", "reference")

    def __init__(self, reference: str) -> None:
        self.reference = reference


class _FileBinding(dict[str, Any]):
    """Wire-compatible binding that owns a host-local source lease."""

    __slots__ = ("lease",)

    def __init__(self, payload: Mapping[str, Any]) -> None:
        super().__init__(payload)
        self.lease: _FileSourceLease | None = None


_FILE_SOURCES: dict[str, _FileSourceEntry] = {}
_FILE_REFERENCE_PREFIX = "file-ref:"
_ABSOLUTE_PATH_FRAGMENT = re.compile(
    r"(?:^|[^A-Za-z0-9/:])(?:[A-Za-z]:[\\/]|/(?!/)|~[\\/])"
)
_PATH_URI_FRAGMENT = re.compile(r"(?:^|[^A-Za-z0-9])(?:file|s3|gs|az)://")
_ANY_URI = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")


def _safe_file_identity(identity: str) -> str:
    value = str(identity)
    if (
        os.path.isabs(value)
        or value.startswith(("/", "~/", "file://", "s3://", "gs://", "az://"))
        or _ANY_URI.match(value) is not None
        or _ABSOLUTE_PATH_FRAGMENT.search(value)
        or _PATH_URI_FRAGMENT.search(value)
    ):
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]
        return f"file:{digest}"
    return value


class ResolvedFileSource:
    """Resolved row-free file source details for a host-side reopen."""

    __slots__ = ("format", "hints", "limits", "lines", "options", "path")

    def __init__(
        self,
        path: Path,
        format: str,
        options: Mapping[str, Any],
        lines: bool = False,
        hints: Mapping[str, str] | None = None,
        limits: Mapping[str, Any] | None = None,
    ) -> None:
        self.path = path
        self.format = format
        self.options = dict(options)
        self.lines = lines
        self.hints = dict(hints or {})
        self.limits = dict(limits or {})


_FILE_OPTION_KEYS = frozenset(
    {
        "delimiter",
        "quotechar",
        "escapechar",
        "doublequote",
        "lineterminator",
        "quoting",
        "skipinitialspace",
        "strict",
        "encoding",
        "null_values",
    }
)
_SOURCE_FORMATS = frozenset({"csv", "tsv", "json", "jsonl"})
_TARGET_WRITE_MODES = frozenset(
    {"append", "overwrite", "merge", "upsert", "partition_replace"}
)
_HINT_ALIASES = {
    "int": "integer",
    "integer": "integer",
    "float": "float",
    "double": "float",
    "number": "float",
    "decimal": "decimal",
    "str": "string",
    "string": "string",
    "bool": "boolean",
    "boolean": "boolean",
    "bytes": "binary",
    "binary": "binary",
    "date": "date",
    "datetime": "datetime",
    "dict": "object",
    "object": "object",
    "list": "array",
    "array": "array",
}
_HINT_TYPES = (
    (bool, "boolean"),
    (int, "integer"),
    (float, "float"),
    (str, "string"),
    (bytes, "binary"),
    (Decimal, "decimal"),
    (_dt.date, "date"),
    (_dt.datetime, "datetime"),
    (dict, "object"),
    (list, "array"),
)


def _normalize_inference_hint(value: Any) -> str | None:
    if isinstance(value, str):
        return _HINT_ALIASES.get(value.casefold())
    for hint_type, normalized in _HINT_TYPES:
        if value is hint_type:
            return normalized
    return None


def _safe_inference_hints(hints: Mapping[str, Any] | None) -> dict[str, str]:
    if hints is None or not isinstance(hints, Mapping):
        return {}
    safe: dict[str, str] = {}
    for key, value in hints.items():
        normalized = _normalize_inference_hint(value)
        if normalized is not None:
            safe[str(key)] = normalized
    return safe


def _safe_inference_limits(
    limits: InferenceLimits | Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if limits is None:
        return None
    if isinstance(limits, InferenceLimits):
        return limits.to_dict()
    if isinstance(limits, Mapping):
        raw = dict(limits)
        try:
            return InferenceLimits.from_dict(raw).to_dict()
        except (TypeError, ValueError):
            return None
    return None


def _safe_binding_requirements(
    requirements: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Keep target requirements row-free and redact path-like identities."""
    payload = _wire_value(dict(requirements or {}))

    def sanitize(value: Any, key: str | None = None) -> Any:
        if isinstance(value, Mapping):
            return {
                str(item_key): sanitize(item_value, str(item_key))
                for item_key, item_value in value.items()
            }
        if isinstance(value, list):
            return [sanitize(item) for item in value]
        if (
            isinstance(value, str)
            and key is not None
            and key.casefold()
            in {
                "identity",
                "path",
                "uri",
            }
        ):
            return _safe_file_identity(value)
        return value

    safe = sanitize(payload)
    return dict(safe) if isinstance(safe, Mapping) else {}


def _validate_inference_hints(hints: Any) -> None:
    if not isinstance(hints, Mapping):
        raise ValueError("INFER_SOURCE_BINDING: inference hints must be a mapping")
    for key, value in hints.items():
        if not isinstance(key, str) or not key:
            raise ValueError(
                "INFER_SOURCE_BINDING: inference hint field names must be strings"
            )
        if _normalize_inference_hint(value) is None:
            raise ValueError(
                f"INFER_SOURCE_BINDING: unsupported inference hint for {key!r}"
            )


def _validate_inference_limits(limits: Any) -> None:
    if not isinstance(limits, Mapping):
        raise ValueError("INFER_SOURCE_BINDING: inference limits must be a mapping")
    try:
        InferenceLimits.from_dict(dict(limits))
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "INFER_SOURCE_BINDING: inference limits are malformed"
        ) from exc


def _safe_file_options(options: Mapping[str, Any] | None) -> dict[str, Any]:
    """Keep only bounded parser options with no provider or secret payloads."""
    safe: dict[str, Any] = {}
    if options is None or not isinstance(options, Mapping):
        return safe
    normalized = {str(key): value for key, value in options.items()}
    for key in sorted(normalized):
        value = normalized[key]
        if key not in _FILE_OPTION_KEYS:
            raise ValueError(f"INFER_SOURCE_BINDING: unsupported file option {key!r}")
        if key == "null_values":
            raise ValueError(
                "INFER_SOURCE_BINDING: null_values cannot cross the durable "
                "boundary because they may contain source or secret values"
            )
        if value is None or isinstance(value, (bool, int, str)):
            safe[key] = value
    return safe


def register_source_factory(
    key: str,
    factory: Callable[[], Any],
    *,
    schema: Any | None = None,
) -> None:
    """Register a host-owned source factory for a records binding.

    Only the key is serialized.  The callable remains process-local and is
    deliberately never walked by the definition serializer. ``schema`` is
    normalized metadata used by static definition validation; registering a
    factory never executes it.
    """
    if not key or not callable(factory):
        raise ValueError("source factory registrations require a key and callable")
    normalized_key = str(key)
    _SOURCE_FACTORIES[normalized_key] = factory
    if schema is None:
        _SOURCE_SCHEMAS.pop(normalized_key, None)
    else:
        _SOURCE_SCHEMAS[normalized_key] = _schema_signature(schema)


def unregister_source_factory(
    key: str, *, expected_factory: Callable[[], Any] | None = None
) -> None:
    """Remove a process-local source factory registration."""
    normalized_key = str(key)
    current = _SOURCE_FACTORIES.get(normalized_key)
    if expected_factory is not None and current is not expected_factory:
        return
    _SOURCE_FACTORIES.pop(normalized_key, None)
    _SOURCE_SCHEMAS.pop(normalized_key, None)


def source_factory(key: str) -> Callable[[], Any] | None:
    """Return a registered source factory, if one exists in this process."""
    return _SOURCE_FACTORIES.get(str(key))


def _source_factory_schema(
    key: str,
) -> tuple[tuple[str, str, bool, bool], ...] | None:
    return _SOURCE_SCHEMAS.get(str(key))


def _source_binding_schema(
    binding: Mapping[str, Any],
) -> tuple[tuple[str, str, bool, bool], ...] | None:
    """Return registered source schema after applying serialized hints."""
    signature = _source_factory_schema(str(binding.get("factory_key") or ""))
    if signature is None:
        return None
    raw_hints = binding.get("hints")
    if not isinstance(raw_hints, Mapping) or not raw_hints:
        return signature

    hints: dict[str, str] = {}
    for field_name, raw_hint in raw_hints.items():
        normalized = _normalize_inference_hint(raw_hint)
        if normalized is not None:
            # The durable wire form keeps ``float`` for compatibility, while
            # record inference normalizes it to the logical ``number`` type.
            hints[str(field_name)] = "number" if normalized == "float" else normalized

    adjusted: list[tuple[str, str, bool, bool]] = []
    for field_name, logical_type, required, nullable in signature:
        hint = hints.get(field_name)
        if hint is None:
            adjusted.append((field_name, logical_type, required, nullable))
            continue
        if logical_type == "unknown":
            adjusted.append((field_name, hint, required, nullable))
            continue
        if logical_type != hint and not {logical_type, hint} <= {
            "integer",
            "number",
        }:
            raise ValueError(
                "INFER_SOURCE_SCHEMA_MISMATCH: source binding hint conflicts "
                f"with registered field {field_name!r}"
            )
        adjusted.append((field_name, hint, required, nullable))
    return tuple(sorted(adjusted))


def _reopened_source_factory_key(
    factory_key: str,
    *,
    hints: Mapping[str, Any] | None,
    limits: InferenceLimits | Mapping[str, Any] | None,
) -> str:
    """Return an isolated identity for a reopened source with overrides."""
    payload = {
        "factory_key": str(factory_key),
        "hints": _safe_inference_hints(hints),
        "limits": _safe_inference_limits(limits),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:32]
    return f"reopen:{digest}"


def records_binding(
    identity: str,
    *,
    factory_key: str | None = None,
    hints: Mapping[str, Any] | None = None,
    limits: InferenceLimits | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    safe_identity = _safe_file_identity(str(identity))
    payload: dict[str, Any] = {
        "version": BINDING_VERSION,
        "kind": "records",
        "identity": safe_identity,
        "resolver": "registry",
        "factory_key": str(factory_key if factory_key is not None else safe_identity),
    }
    safe_hints = _safe_inference_hints(hints)
    safe_limits = _safe_inference_limits(limits)
    if safe_hints:
        payload["hints"] = safe_hints
    if safe_limits is not None:
        payload["limits"] = safe_limits
    return payload


def file_binding(
    format: str,
    path: str | Path,
    *,
    identity: str,
    options: Mapping[str, Any] | None = None,
    lines: bool | None = None,
    hints: Mapping[str, Any] | None = None,
    limits: InferenceLimits | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a stable, row-free local file binding."""
    safe_options = _safe_file_options(options)
    safe_hints = _safe_inference_hints(hints)
    safe_limits = _safe_inference_limits(limits)
    reference = _file_reference(path)
    payload: dict[str, Any] = {
        "version": BINDING_VERSION,
        "kind": "file",
        "format": format,
        "identity": _safe_file_identity(str(identity)),
        "uri": reference,
        "options": safe_options,
    }
    if lines is not None:
        payload["lines"] = bool(lines)
    if safe_hints:
        payload["hints"] = safe_hints
    if safe_limits is not None:
        payload["limits"] = safe_limits
    return _FileBinding(payload)


def _file_reference(path: str | Path) -> str:
    """Register a local path and return a stable, non-path wire reference."""
    if isinstance(path, str) and path.startswith(_FILE_REFERENCE_PREFIX):
        return path
    resolved = Path(path).expanduser().resolve()
    digest = hashlib.sha256(str(resolved).encode("utf-8")).hexdigest()[:32]
    reference = f"{_FILE_REFERENCE_PREFIX}{digest}"
    _FILE_SOURCES.setdefault(reference, _FileSourceEntry(resolved))
    return reference


def _release_file_lease(
    reference: str, token: weakref.ReferenceType[_FileSourceLease]
) -> None:
    entry = _FILE_SOURCES.get(reference)
    if entry is None:
        return
    entry.leases.discard(token)
    if not entry.leases:
        _FILE_SOURCES.pop(reference, None)


def _retain_file_source(
    reference: str, path: str | Path | None = None
) -> _FileSourceLease:
    """Return a host-local lease for a registered file reference."""
    normalized_reference = str(reference)
    entry = _FILE_SOURCES.get(normalized_reference)
    if entry is None and path is not None:
        entry = _FileSourceEntry(Path(path).expanduser().resolve())
        _FILE_SOURCES[normalized_reference] = entry
    if entry is None:
        raise ValueError("INFER_SOURCE_UNRESOLVABLE: source file is unavailable")
    lease = _FileSourceLease(normalized_reference)
    token = weakref.ref(
        lease,
        lambda released, ref=normalized_reference: _release_file_lease(ref, released),
    )
    entry.leases.add(token)
    return lease


def unregister_file_source(reference: str) -> None:
    """Release a process-local file reference registration."""
    _FILE_SOURCES.pop(str(reference), None)


def _registered_file_path(reference: str) -> Path | None:
    entry = _FILE_SOURCES.get(reference)
    return entry.path if entry is not None else None


def provider_binding(identity: str, provider: str) -> dict[str, Any]:
    """Describe a provider source that must be explicitly rebound to replay."""
    return {
        "version": BINDING_VERSION,
        "kind": "provider",
        "provider": provider,
        "identity": _safe_file_identity(str(identity)),
        "resolver": "explicit_rebind",
    }


def target_binding(
    observation: TargetObservation | None,
    *,
    identity: str,
    requirements: Mapping[str, Any] | None = None,
    write_mode: str = "append",
) -> dict[str, Any]:
    """Serialize target identity, revision, intent, and requirements separately."""
    observed_identity = observation.identity if observation is not None else None
    is_observed = (
        observation is not None
        and observation.schema is not None
        and observation.inspector not in {"provided", "normalized"}
    )
    return {
        "version": BINDING_VERSION,
        "kind": "target",
        "identity": _safe_file_identity(str(observed_identity or identity)),
        "revision": observation.revision if observation is not None else None,
        "write_mode": str(write_mode),
        "requirements": _safe_binding_requirements(requirements),
        "observed": is_observed,
    }


def _source_binding_for_rebind(
    source: str | Path | Mapping[str, Any],
    *,
    format: str | None = None,
    template: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if isinstance(source, Mapping):
        raw = dict(source)
        _validate_source_binding_shape(raw)
        kind = raw["kind"]
        if kind == "records":
            return records_binding(
                str(raw.get("identity") or "records"),
                factory_key=str(raw["factory_key"]),
                hints=(
                    raw.get("hints") if isinstance(raw.get("hints"), Mapping) else None
                ),
                limits=(
                    raw.get("limits")
                    if isinstance(raw.get("limits"), Mapping)
                    else None
                ),
            )
        if kind == "file":
            options = raw.get("options")
            _validate_file_options(options if isinstance(options, Mapping) else {})
            uri = str(raw["uri"])
            if not uri.startswith(_FILE_REFERENCE_PREFIX):
                uri = _file_reference(uri)
            return file_binding(
                str(raw["format"]),
                uri,
                identity=str(raw.get("identity") or raw["uri"]),
                options=options if isinstance(options, Mapping) else None,
                lines=(bool(raw["lines"]) if "lines" in raw else None),
                hints=raw.get("hints")
                if isinstance(raw.get("hints"), Mapping)
                else None,
                limits=raw.get("limits")
                if isinstance(raw.get("limits"), Mapping)
                else None,
            )
        return provider_binding(
            str(raw.get("identity") or "provider"), str(raw["provider"])
        )
    path = Path(source)
    suffix = path.suffix.lower()
    source_format = format or (
        "jsonl"
        if suffix == ".jsonl"
        else "json"
        if suffix == ".json"
        else suffix.lstrip(".")
    )
    if source_format not in _SOURCE_FORMATS:
        raise ValueError(
            f"INFER_SOURCE_UNSUPPORTED: cannot durably bind {source_format!r} source"
        )
    resolved = str(path.expanduser().resolve())
    identity = f"{source_format}:{hashlib.sha256(resolved.encode()).hexdigest()[:20]}"
    template_options = (
        template.get("options")
        if isinstance(template, Mapping)
        and isinstance(template.get("options"), Mapping)
        else None
    )
    template_format = (
        template.get("format")
        if isinstance(template, Mapping) and isinstance(template.get("format"), str)
        else None
    )
    template_hints = (
        template.get("hints")
        if isinstance(template, Mapping) and isinstance(template.get("hints"), Mapping)
        else None
    )
    template_limits = (
        template.get("limits")
        if isinstance(template, Mapping) and isinstance(template.get("limits"), Mapping)
        else None
    )
    return file_binding(
        source_format,
        path,
        identity=identity,
        options=(
            template_options
            if source_format in {"csv", "tsv"} and template_format == source_format
            else None
        ),
        lines=True if source_format == "jsonl" else None,
        hints=template_hints,
        limits=template_limits,
    )


def _file_binding_template(definition: PipelineDefinition) -> Mapping[str, Any] | None:
    for node in definition.nodes:
        if node.kind != "source":
            continue
        binding = node.bindings.get("source")
        if isinstance(binding, Mapping) and binding.get("kind") == "file":
            return binding
    return None


def rebind_definition(
    definition: PipelineDefinition,
    *,
    source: str | Path | Mapping[str, Any] | None = None,
    format: str | None = None,
    target: Mapping[str, Any] | None = None,
) -> PipelineDefinition:
    """Return a definition with explicit source and/or target rebinding.

    Rebinding changes only row-free binding metadata.  Local file rebinding
    performs a bounded schema check, but never embeds rows or changes
    contracts silently.
    """
    if not isinstance(definition, PipelineDefinition):
        raise TypeError("definition must be a PipelineDefinition")
    source_payload = (
        _source_binding_for_rebind(
            source,
            format=format,
            template=(
                _file_binding_template(definition)
                if not isinstance(source, Mapping)
                else None
            ),
        )
        if source is not None
        else None
    )
    target_payload = None
    if target is not None:
        raw_target = dict(target)
        validate_target_binding(raw_target)
        target_payload = {
            "version": BINDING_VERSION,
            "kind": "target",
            "identity": _safe_file_identity(str(raw_target["identity"])),
            "revision": raw_target.get("revision"),
            "write_mode": str(raw_target.get("write_mode", "append")),
            "requirements": _safe_binding_requirements(
                raw_target.get("requirements")
                if isinstance(raw_target.get("requirements"), Mapping)
                else None
            ),
            "observed": bool(raw_target.get("observed", False)),
        }
    source_lease: _FileSourceLease | None = None
    if source_payload is not None:
        if source_payload.get("kind") == "file":
            source_lease = _retain_file_source(str(source_payload["uri"]))
            if isinstance(source_payload, _FileBinding):
                source_payload.lease = source_lease
            _validate_rebound_file_source(definition, source_payload)
        elif source_payload.get("kind") == "records":
            # An unresolved factory may be registered by the eventual host,
            # but validate its schema now whenever this host has metadata for
            # it. This prevents serialized hints from silently changing the
            # source contract.
            if (
                _source_factory_schema(str(source_payload.get("factory_key") or ""))
                is not None
            ):
                validate_source_binding_against_definition(definition, source_payload)
    if target_payload is not None:
        _validate_rebound_target(definition, target_payload)
    nodes: list[NodeDefinition] = []
    for node in definition.nodes:
        bindings = dict(node.bindings)
        metadata = dict(node.metadata)
        if source_payload is not None and node.kind == "source":
            bindings["source"] = source_payload
            metadata = _update_binding_metadata(metadata, source_payload=source_payload)
        if target_payload is not None and node.kind == "sink":
            bindings["target"] = target_payload
            metadata = _update_binding_metadata(metadata, target_payload=target_payload)
        nodes.append(replace(node, bindings=bindings, metadata=metadata))
    contracts = tuple(
        replace(
            contract,
            metadata=_update_binding_metadata(
                contract.metadata,
                source_payload=source_payload
                if isinstance(contract.metadata.get("etlantic.inference"), Mapping)
                and "source_binding" in contract.metadata["etlantic.inference"]
                else None,
            ),
        )
        for contract in definition.contracts
    )
    updated_metadata = _update_binding_metadata(
        definition.metadata,
        source_payload=source_payload,
        target_payload=target_payload,
    )
    updated = replace(
        definition,
        contracts=contracts,
        nodes=tuple(nodes),
        metadata=updated_metadata,
        fingerprint=None,
        runtime_source_leases=(
            definition.runtime_source_leases
            + ((source_lease,) if source_lease is not None else ())
        ),
    )
    return updated.with_fingerprint(pipeline_fingerprint(updated))


def _update_binding_metadata(
    metadata: Mapping[str, Any],
    *,
    source_payload: Mapping[str, Any] | None = None,
    target_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Keep duplicated inference binding metadata aligned with node bindings."""
    updated = dict(metadata)
    raw_inference = updated.get("etlantic.inference")
    inference = dict(raw_inference) if isinstance(raw_inference, Mapping) else {}
    if source_payload is not None:
        inference["source_binding"] = dict(source_payload)
    if target_payload is not None:
        inference["target_binding"] = dict(target_payload)
        inference["target_requirements"] = target_payload.get("requirements")
        inference["target_revision"] = target_payload.get("revision")
        inference["write_mode"] = target_payload.get("write_mode")
    if (
        source_payload is not None
        or target_payload is not None
        or raw_inference is not None
    ):
        updated["etlantic.inference"] = inference
    return updated


def _contract_for_node(definition: PipelineDefinition, node: NodeDefinition) -> Any:
    if node.contract_id is None:
        raise ValueError(
            "INFER_REBIND_CONTRACT: rebound node does not declare a source contract"
        )
    for contract in definition.contracts:
        if (
            contract.identity == node.contract_id
            or contract.authoring_id == node.contract_id
        ):
            return contract
    raise ValueError(
        f"INFER_REBIND_CONTRACT: rebound node references unknown contract {node.contract_id!r}"
    )


def _normalized_schema_from_contract(contract: Any) -> Any:
    from etlantic.schema_drift import NormalizedField, NormalizedSchema

    return NormalizedSchema(
        contract.identity,
        tuple(
            NormalizedField(
                field.name,
                field.type,
                required=field.required,
                nullable=field.nullable,
            )
            for field in contract.fields
        ),
    )


def _schema_signature(schema: Any) -> tuple[tuple[str, str, bool, bool], ...]:
    return tuple(
        sorted(
            (
                field.name,
                field.logical_type,
                field.required,
                field.nullable,
            )
            for field in schema.fields
        )
    )


def validate_source_binding_against_definition(
    definition: PipelineDefinition,
    binding: Mapping[str, Any],
    *,
    source_node: NodeDefinition | None = None,
) -> None:
    """Verify a source binding still satisfies its source contract.

    The binding shape and host-side resolver are validated separately by
    ``validate_source_binding``. This check performs the definition-aware
    schema comparison needed when a serialized definition is loaded again.
    File bindings are reopened only to inspect their normalized schema. Record
    bindings use schema metadata captured at registration time, so validation
    never executes an arbitrary source factory.
    """
    source_nodes = (
        [source_node]
        if source_node is not None
        else [node for node in definition.nodes if node.kind == "source"]
    )
    if not source_nodes:
        raise ValueError("INFER_SOURCE_REBIND: definition has no source node")
    kind = binding.get("kind")
    if kind == "records":
        rebound_signature = _source_binding_schema(binding)
        if rebound_signature is None:
            raise ValueError(
                "INFER_SOURCE_SCHEMA_UNVERIFIED: records source factory has no "
                "registered schema metadata"
            )
    elif kind == "file":
        try:
            dataset = reopen_source_binding(binding)
            error_diagnostics = [
                diagnostic
                for diagnostic in getattr(dataset, "diagnostics", ())
                if getattr(
                    getattr(diagnostic, "severity", None),
                    "value",
                    getattr(diagnostic, "severity", None),
                )
                == "error"
                or (
                    isinstance(diagnostic, Mapping)
                    and str(diagnostic.get("severity", "")).lower() == "error"
                )
            ]
            if error_diagnostics:
                raise ValueError(
                    "INFER_SOURCE_REBIND: rebound source reported error diagnostics"
                )
            rebound_signature = _schema_signature(dataset.schema)
        except Exception as exc:
            raise ValueError(
                "INFER_SOURCE_REBIND: rebound source could not be inspected safely"
            ) from exc
    else:
        raise ValueError(
            "INFER_SOURCE_UNSUPPORTED: source binding requires an explicit rebind"
        )
    for node in source_nodes:
        contract = _contract_for_node(definition, node)
        expected_schema = _normalized_schema_from_contract(contract)
        if rebound_signature != _schema_signature(expected_schema):
            raise ValueError(
                "INFER_SOURCE_SCHEMA_MISMATCH: rebound source schema does not "
                f"match contract {contract.identity!r}"
            )


def _validate_rebound_file_source(
    definition: PipelineDefinition, binding: Mapping[str, Any]
) -> None:
    """Verify a local file rebinding still satisfies every source contract."""
    validate_source_binding_against_definition(definition, binding)


def validate_file_binding_against_definition(
    definition: PipelineDefinition, binding: Mapping[str, Any]
) -> None:
    """Verify a generated local file binding before durable export."""
    if binding.get("kind") != "file":
        raise ValueError("INFER_SOURCE_REBIND: expected a file source binding")
    validate_source_binding_against_definition(definition, binding)


def validate_target_binding_against_definition(
    definition: PipelineDefinition,
    binding: Mapping[str, Any],
    *,
    sink_node: NodeDefinition | None = None,
) -> None:
    """Verify a target binding's schema against its sink contract."""
    if not binding.get("observed") and not binding.get("requirements"):
        return
    requirements = binding.get("requirements")
    if not isinstance(requirements, Mapping) or not requirements:
        raise ValueError(
            "INFER_TARGET_BINDING: observed target rebinding requires a schema"
        )
    from etlantic.inference.targets import check_write_compatibility
    from etlantic.schema_drift import NormalizedSchema

    try:
        target_schema = NormalizedSchema.from_dict(mutable_copy(requirements))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            "INFER_TARGET_BINDING: observed target schema is malformed"
        ) from exc
    sink_nodes = (
        [sink_node]
        if sink_node is not None
        else [node for node in definition.nodes if node.kind == "sink"]
    )
    if not sink_nodes:
        raise ValueError("INFER_TARGET_REBIND: definition has no sink node")
    for node in sink_nodes:
        contract = _contract_for_node(definition, node)
        source_schema = _normalized_schema_from_contract(contract)
        compatibility = check_write_compatibility(
            source_schema,
            target_schema,
            mode=str(binding.get("write_mode", "append")),
        )
        if not compatibility.compatible or compatibility.casts:
            codes = sorted({item.code for item in compatibility.diagnostics})
            if compatibility.casts:
                codes.append("INFER_RUNTIME_CONVERSION")
            raise ValueError(
                "INFER_TARGET_WRITE_UNQUALIFIED: rebound target is not "
                f"compatible with contract {contract.identity!r} "
                f"({', '.join(codes) or 'unknown'})"
            )


def _validate_rebound_target(
    definition: PipelineDefinition, binding: Mapping[str, Any]
) -> None:
    """Verify an observed target rebinding against the final sink contract."""
    validate_target_binding_against_definition(definition, binding)


def _validate_source_binding_shape(binding: Mapping[str, Any]) -> None:
    if not isinstance(binding, Mapping):
        raise ValueError("INFER_SOURCE_BINDING: source binding must be a mapping")
    version = binding.get("version")
    if isinstance(version, bool) or not isinstance(version, int):
        raise ValueError("INFER_SOURCE_BINDING: invalid binding version")
    if version != BINDING_VERSION:
        raise ValueError("INFER_SOURCE_BINDING: unsupported source binding version")
    kind = binding.get("kind")
    if kind == "records":
        if binding.get("resolver") != "registry":
            raise ValueError(
                "INFER_SOURCE_BINDING: records binding must use the registry resolver"
            )
        if not str(binding.get("factory_key") or ""):
            raise ValueError(
                "INFER_SOURCE_BINDING: records binding requires a factory key"
            )
        if "hints" in binding:
            _validate_inference_hints(binding["hints"])
        if "limits" in binding:
            _validate_inference_limits(binding["limits"])
        return
    if kind == "file":
        format_name = binding.get("format")
        if not isinstance(format_name, str) or format_name not in _SOURCE_FORMATS:
            raise ValueError("INFER_SOURCE_BINDING: unsupported file source format")
        if not str(binding.get("uri") or ""):
            raise ValueError("INFER_SOURCE_BINDING: file binding requires a URI")
        options = binding.get("options", {})
        if not isinstance(options, Mapping):
            raise ValueError("INFER_SOURCE_BINDING: file options must be a mapping")
        _validate_file_options(options)
        if "lines" in binding and not isinstance(binding["lines"], bool):
            raise ValueError("INFER_SOURCE_BINDING: file lines must be boolean")
        if "hints" in binding:
            _validate_inference_hints(binding["hints"])
        if "limits" in binding:
            _validate_inference_limits(binding["limits"])
        return
    if kind == "provider":
        if not str(binding.get("provider") or ""):
            raise ValueError(
                "INFER_SOURCE_BINDING: provider binding requires a provider"
            )
        if binding.get("resolver") != "explicit_rebind":
            raise ValueError(
                "INFER_SOURCE_BINDING: provider binding requires explicit rebinding"
            )
        return
    raise ValueError("INFER_SOURCE_BINDING: unsupported source binding kind")


def validate_target_binding(
    binding: Mapping[str, Any], *, check_capabilities: bool = True
) -> None:
    """Validate the row-free shape of a durable target binding."""
    if not isinstance(binding, Mapping):
        raise ValueError("INFER_TARGET_BINDING: target binding must be a mapping")
    version = binding.get("version")
    if isinstance(version, bool) or not isinstance(version, int):
        raise ValueError("INFER_TARGET_BINDING: invalid binding version")
    if version != BINDING_VERSION:
        raise ValueError("INFER_TARGET_BINDING: unsupported binding version")
    if not isinstance(binding.get("kind"), str) or binding.get("kind") != "target":
        raise ValueError("INFER_TARGET_BINDING: binding kind must be target")
    if not str(binding.get("identity") or ""):
        raise ValueError("INFER_TARGET_BINDING: target binding requires an identity")
    if binding.get("revision") is not None and not isinstance(
        binding.get("revision"), str
    ):
        raise ValueError("INFER_TARGET_BINDING: target revision must be a string")
    write_mode = binding.get("write_mode", "append")
    if not isinstance(write_mode, str) or write_mode not in _TARGET_WRITE_MODES:
        raise ValueError("INFER_TARGET_BINDING: unsupported target write mode")
    requirements = binding.get("requirements", {})
    if not isinstance(requirements, Mapping):
        raise ValueError("INFER_TARGET_BINDING: target requirements must be a mapping")
    if not isinstance(binding.get("observed", False), bool):
        raise ValueError("INFER_TARGET_BINDING: observed must be boolean")
    if binding.get("observed", False) and not requirements:
        raise ValueError(
            "INFER_TARGET_BINDING: observed target requires normalized requirements"
        )
    if requirements:
        _validate_target_requirements(requirements)
        if binding.get("observed", False) and check_capabilities:
            capabilities = requirements.get("metadata", {}).get("capabilities")
            if not _supports_write_mode(
                capabilities, str(binding.get("write_mode", "append"))
            ):
                raise ValueError(
                    "INFER_TARGET_BINDING: target does not advertise the requested "
                    f"write mode {binding.get('write_mode', 'append')!r}"
                )


def _validate_file_options(options: Mapping[str, Any]) -> None:
    """Validate the parser subset that can cross the durable boundary."""
    unknown = set(str(key) for key in options) - _FILE_OPTION_KEYS
    if unknown:
        raise ValueError(
            f"INFER_SOURCE_BINDING: unsupported file options {sorted(unknown)!r}"
        )
    for key, value in options.items():
        name = str(key)
        if name == "null_values":
            raise ValueError(
                "INFER_SOURCE_BINDING: null_values cannot cross the durable "
                "boundary because they may contain source or secret values"
            )
        if name in {"delimiter", "quotechar", "escapechar"}:
            if value is not None and (not isinstance(value, str) or len(value) != 1):
                raise ValueError(
                    f"INFER_SOURCE_BINDING: file option {name!r} must be one character"
                )
        elif name == "encoding":
            if not isinstance(value, str) or not value:
                raise ValueError(
                    "INFER_SOURCE_BINDING: file option 'encoding' must be a string"
                )
        elif name in {"doublequote", "strict"} and not isinstance(value, bool):
            raise ValueError(
                f"INFER_SOURCE_BINDING: file option {name!r} must be boolean"
            )
        elif name == "skipinitialspace" and not isinstance(value, bool):
            raise ValueError(
                "INFER_SOURCE_BINDING: file option 'skipinitialspace' must be boolean"
            )
        elif name == "quoting" and (
            isinstance(value, bool) or not isinstance(value, int) or value < 0
        ):
            raise ValueError(
                "INFER_SOURCE_BINDING: file option 'quoting' must be a non-negative integer"
            )
        elif name == "lineterminator" and (not isinstance(value, str) or not value):
            raise ValueError(
                "INFER_SOURCE_BINDING: file option 'lineterminator' must be a non-empty string"
            )


def _validate_target_requirements(requirements: Mapping[str, Any]) -> None:
    """Validate a serialized normalized target schema and its capabilities."""
    from etlantic.schema_drift import NormalizedSchema

    if requirements.get("version", 1) != 1:
        raise ValueError("INFER_TARGET_BINDING: unsupported target schema version")
    if not isinstance(requirements.get("identity"), str) or not requirements.get(
        "identity"
    ):
        raise ValueError("INFER_TARGET_BINDING: target schema identity is required")
    fields = requirements.get("fields")
    if not isinstance(fields, (list, tuple)) or any(
        not isinstance(field, Mapping)
        or not isinstance(field.get("name"), str)
        or not isinstance(field.get("logical_type"), str)
        for field in fields
    ):
        raise ValueError("INFER_TARGET_BINDING: target schema fields are malformed")
    if requirements.get("fingerprint") is not None and not isinstance(
        requirements.get("fingerprint"), str
    ):
        raise ValueError("INFER_TARGET_BINDING: target schema fingerprint is malformed")
    try:
        NormalizedSchema.from_dict(mutable_copy(requirements))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            "INFER_TARGET_BINDING: target requirements are not a normalized schema"
        ) from exc
    metadata = requirements.get("metadata", {})
    if not isinstance(metadata, Mapping):
        raise ValueError("INFER_TARGET_BINDING: target metadata must be a mapping")
    if "capabilities" in metadata:
        capabilities = metadata["capabilities"]
        if isinstance(capabilities, Mapping):
            modes = capabilities.get("write_modes", capabilities.get("modes"))
            if modes is not None and (
                not isinstance(modes, (list, tuple, set, frozenset))
                or not all(isinstance(mode, str) for mode in modes)
            ):
                raise ValueError(
                    "INFER_TARGET_BINDING: target write modes must be a sequence"
                )
        elif not isinstance(capabilities, (list, tuple, set, frozenset)):
            raise ValueError("INFER_TARGET_BINDING: target capabilities are malformed")


def _supports_write_mode(capabilities: Any, mode: str) -> bool:
    if isinstance(capabilities, Mapping):
        modes = capabilities.get("write_modes", capabilities.get("modes"))
        return isinstance(modes, (list, tuple, set, frozenset)) and mode in modes
    if isinstance(capabilities, (list, tuple, set, frozenset)):
        return mode in capabilities
    return False


def validate_source_binding(binding: Mapping[str, Any]) -> None:
    """Validate that a durable source binding can be reopened in this host."""
    _validate_source_binding_shape(binding)
    kind = binding.get("kind")
    if kind == "records":
        key = str(binding.get("factory_key") or "")
        if source_factory(key) is None:
            raise ValueError(
                f"INFER_SOURCE_UNRESOLVABLE: no source factory registered for {key!r}"
            )
        return
    if kind == "file":
        reference = str(binding.get("uri") or "")
        path = _registered_file_path(reference)
        if path is None:
            raise ValueError(
                "INFER_SOURCE_UNRESOLVABLE: file binding requires an explicit "
                "host-side rebind"
            )
        if not path.is_file():
            raise ValueError("INFER_SOURCE_UNRESOLVABLE: source file is unavailable")
        return
    raise ValueError(
        "INFER_SOURCE_UNSUPPORTED: source binding requires an explicit rebind"
    )


def resolve_source_binding(binding: Mapping[str, Any]) -> Any:
    """Resolve a registered records or local file binding for execution."""
    validate_source_binding(binding)
    kind = binding.get("kind")
    if kind == "records":
        key = str(binding.get("factory_key") or "")
        factory = source_factory(key)
        assert factory is not None
        return factory()
    if kind == "file":
        reference = str(binding.get("uri") or "")
        path = _registered_file_path(reference)
        if path is None:
            raise ValueError(
                "INFER_SOURCE_UNRESOLVABLE: file binding requires an explicit "
                "host-side rebind"
            )
        return ResolvedFileSource(
            path,
            str(binding["format"]),
            binding.get("options", {})
            if isinstance(binding.get("options", {}), Mapping)
            else {},
            bool(binding.get("lines", False)),
            binding.get("hints") if isinstance(binding.get("hints"), Mapping) else {},
            binding.get("limits") if isinstance(binding.get("limits"), Mapping) else {},
        )
    raise AssertionError("validated source binding has an unsupported kind")


def reopen_source_binding(
    binding: Mapping[str, Any],
    *,
    name: str | None = None,
    hints: Mapping[str, Any] | None = None,
    limits: Any | None = None,
) -> Any:
    """Reopen a durable binding through the public inference facade."""
    resolved = resolve_source_binding(binding)
    if isinstance(resolved, ResolvedFileSource):
        from .facade import read_csv, read_json

        source_name = name or str(binding.get("identity") or "source")
        resolved_hints = hints if hints is not None else resolved.hints or None
        resolved_limits = limits
        if resolved_limits is None and resolved.limits:
            resolved_limits = InferenceLimits.from_dict(resolved.limits)
        if resolved.format in {"csv", "tsv"}:
            options = dict(resolved.options)
            if resolved.format == "tsv":
                options.setdefault("delimiter", "\t")
            return read_csv(
                str(resolved.path),
                name=source_name,
                options=options,
                hints=resolved_hints,
                limits=resolved_limits,
            )
        return read_json(
            str(resolved.path),
            name=source_name,
            lines=resolved.lines or resolved.format == "jsonl",
            hints=resolved_hints,
            limits=resolved_limits,
        )
    from .facade import from_records

    factory_key = str(binding.get("factory_key") or "")
    factory = source_factory(factory_key)
    resolved_hints = hints
    if resolved_hints is None and isinstance(binding.get("hints"), Mapping):
        resolved_hints = binding["hints"]
    resolved_limits = limits
    if resolved_limits is None and isinstance(binding.get("limits"), Mapping):
        resolved_limits = InferenceLimits.from_dict(dict(binding["limits"]))
    reopened_key = factory_key
    if hints is not None or limits is not None:
        reopened_key = _reopened_source_factory_key(
            factory_key,
            hints=resolved_hints,
            limits=resolved_limits,
        )
    return from_records(
        resolved,
        name=name or str(binding.get("identity") or "records"),
        hints=resolved_hints,
        limits=resolved_limits,
        source_factory=factory,
        source_key=reopened_key,
    )
