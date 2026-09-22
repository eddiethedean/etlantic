"""Row-free, versioned bindings used by inferred pipeline definitions."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from etlantic.authoring.definition import NodeDefinition, PipelineDefinition
from etlantic.authoring.serialize import pipeline_fingerprint

from .types import TargetObservation, _wire_value

BINDING_VERSION = 1

_SOURCE_FACTORIES: dict[str, Callable[[], Any]] = {}
_FILE_SOURCES: dict[str, Path] = {}
_FILE_REFERENCE_PREFIX = "file-ref:"


def _safe_file_identity(identity: str) -> str:
    value = str(identity)
    if value.startswith(("/", "~/", "file://", "s3://", "gs://", "az://")):
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]
        return f"file:{digest}"
    return value


class ResolvedFileSource:
    """Resolved row-free file source details for a host-side reopen."""

    __slots__ = ("format", "lines", "options", "path")

    def __init__(
        self,
        path: Path,
        format: str,
        options: Mapping[str, Any],
        lines: bool = False,
    ) -> None:
        self.path = path
        self.format = format
        self.options = dict(options)
        self.lines = lines


_FILE_OPTION_KEYS = frozenset(
    {
        "delimiter",
        "quotechar",
        "escapechar",
        "doublequote",
        "strict",
        "encoding",
        "null_values",
    }
)
_SOURCE_FORMATS = frozenset({"csv", "tsv", "json", "jsonl"})
_TARGET_WRITE_MODES = frozenset(
    {"append", "overwrite", "merge", "upsert", "partition_replace"}
)


def _safe_file_options(options: Mapping[str, Any] | None) -> dict[str, Any]:
    """Keep only bounded parser options with no provider or secret payloads."""
    safe: dict[str, Any] = {}
    if options is None or not isinstance(options, Mapping):
        return safe
    normalized = {str(key): value for key, value in options.items()}
    for key in sorted(normalized):
        value = normalized[key]
        if key not in _FILE_OPTION_KEYS:
            continue
        if key == "null_values":
            if isinstance(value, (list, tuple, set, frozenset)):
                values = list(value)
                if isinstance(value, (set, frozenset)):
                    values.sort(key=str)
                safe[key] = [str(item) for item in values[:256]]
            continue
        if value is None or isinstance(value, (bool, int, str)):
            safe[key] = value
    return safe


def register_source_factory(key: str, factory: Callable[[], Any]) -> None:
    """Register a host-owned source factory for a records binding.

    Only the key is serialized.  The callable remains process-local and is
    deliberately never walked by the definition serializer.
    """
    if not key or not callable(factory):
        raise ValueError("source factory registrations require a key and callable")
    _SOURCE_FACTORIES[str(key)] = factory


def unregister_source_factory(key: str) -> None:
    """Remove a process-local source factory registration."""
    _SOURCE_FACTORIES.pop(str(key), None)


def source_factory(key: str) -> Callable[[], Any] | None:
    """Return a registered source factory, if one exists in this process."""
    return _SOURCE_FACTORIES.get(str(key))


def records_binding(identity: str, *, factory_key: str | None = None) -> dict[str, Any]:
    return {
        "version": BINDING_VERSION,
        "kind": "records",
        "identity": str(identity),
        "resolver": "registry",
        "factory_key": str(factory_key or identity),
    }


def file_binding(
    format: str,
    path: str | Path,
    *,
    identity: str,
    options: Mapping[str, Any] | None = None,
    lines: bool | None = None,
) -> dict[str, Any]:
    """Create a stable, row-free local file binding."""
    reference = _file_reference(path)
    payload: dict[str, Any] = {
        "version": BINDING_VERSION,
        "kind": "file",
        "format": format,
        "identity": _safe_file_identity(str(identity)),
        "uri": reference,
        "options": _safe_file_options(options),
    }
    if lines is not None:
        payload["lines"] = bool(lines)
    return payload


def _file_reference(path: str | Path) -> str:
    """Register a local path and return a stable, non-path wire reference."""
    if isinstance(path, str) and path.startswith(_FILE_REFERENCE_PREFIX):
        return path
    resolved = Path(path).expanduser().resolve()
    digest = hashlib.sha256(str(resolved).encode("utf-8")).hexdigest()[:32]
    reference = f"{_FILE_REFERENCE_PREFIX}{digest}"
    _FILE_SOURCES[reference] = resolved
    return reference


def _registered_file_path(reference: str) -> Path | None:
    return _FILE_SOURCES.get(reference)


def provider_binding(identity: str, provider: str) -> dict[str, Any]:
    """Describe a provider source that must be explicitly rebound to replay."""
    return {
        "version": BINDING_VERSION,
        "kind": "provider",
        "provider": provider,
        "identity": str(identity),
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
    return {
        "version": BINDING_VERSION,
        "kind": "target",
        "identity": str(observed_identity or identity),
        "revision": observation.revision if observation is not None else None,
        "write_mode": str(write_mode),
        "requirements": _wire_value(dict(requirements or {})),
        "observed": observation is not None and observation.schema is not None,
    }


def _source_binding_for_rebind(
    source: str | Path | Mapping[str, Any], *, format: str | None = None
) -> dict[str, Any]:
    if isinstance(source, Mapping):
        raw = dict(source)
        _validate_source_binding_shape(raw)
        kind = raw["kind"]
        if kind == "records":
            return records_binding(
                str(raw.get("identity") or "records"),
                factory_key=str(raw["factory_key"]),
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
    return file_binding(
        source_format,
        path,
        identity=identity,
        lines=True if source_format == "jsonl" else None,
    )


def rebind_definition(
    definition: PipelineDefinition,
    *,
    source: str | Path | Mapping[str, Any] | None = None,
    format: str | None = None,
    target: Mapping[str, Any] | None = None,
) -> PipelineDefinition:
    """Return a definition with explicit source and/or target rebinding.

    Rebinding changes only row-free binding metadata.  It never reads a
    source, embeds rows, or silently changes contracts.
    """
    if not isinstance(definition, PipelineDefinition):
        raise TypeError("definition must be a PipelineDefinition")
    source_payload = (
        _source_binding_for_rebind(source, format=format)
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
            "identity": str(raw_target["identity"]),
            "revision": raw_target.get("revision"),
            "write_mode": str(raw_target.get("write_mode", "append")),
            "requirements": _wire_value(
                dict(raw_target.get("requirements") or {})
            ),
            "observed": bool(raw_target.get("observed", False)),
        }
    nodes: list[NodeDefinition] = []
    for node in definition.nodes:
        bindings = dict(node.bindings)
        if source_payload is not None and node.kind == "source":
            bindings["source"] = source_payload
        if target_payload is not None and node.kind == "sink":
            bindings["target"] = target_payload
        nodes.append(replace(node, bindings=bindings))
    updated = replace(definition, nodes=tuple(nodes), fingerprint=None)
    return updated.with_fingerprint(pipeline_fingerprint(updated))


def _validate_source_binding_shape(binding: Mapping[str, Any]) -> None:
    if not isinstance(binding, Mapping):
        raise ValueError("INFER_SOURCE_BINDING: source binding must be a mapping")
    try:
        version = int(binding.get("version", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("INFER_SOURCE_BINDING: invalid binding version") from exc
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
        return
    if kind == "file":
        if binding.get("format") not in _SOURCE_FORMATS:
            raise ValueError("INFER_SOURCE_BINDING: unsupported file source format")
        if not str(binding.get("uri") or ""):
            raise ValueError("INFER_SOURCE_BINDING: file binding requires a URI")
        options = binding.get("options", {})
        if not isinstance(options, Mapping):
            raise ValueError("INFER_SOURCE_BINDING: file options must be a mapping")
        _validate_file_options(options)
        if "lines" in binding and not isinstance(binding["lines"], bool):
            raise ValueError("INFER_SOURCE_BINDING: file lines must be boolean")
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


def validate_target_binding(binding: Mapping[str, Any]) -> None:
    """Validate the row-free shape of a durable target binding."""
    if not isinstance(binding, Mapping):
        raise ValueError("INFER_TARGET_BINDING: target binding must be a mapping")
    try:
        version = int(binding.get("version", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("INFER_TARGET_BINDING: invalid binding version") from exc
    if version != BINDING_VERSION:
        raise ValueError("INFER_TARGET_BINDING: unsupported binding version")
    if binding.get("kind") != "target":
        raise ValueError("INFER_TARGET_BINDING: binding kind must be target")
    if not str(binding.get("identity") or ""):
        raise ValueError("INFER_TARGET_BINDING: target binding requires an identity")
    if binding.get("revision") is not None and not isinstance(
        binding.get("revision"), str
    ):
        raise ValueError("INFER_TARGET_BINDING: target revision must be a string")
    if binding.get("write_mode", "append") not in _TARGET_WRITE_MODES:
        raise ValueError("INFER_TARGET_BINDING: unsupported target write mode")
    requirements = binding.get("requirements", {})
    if not isinstance(requirements, Mapping):
        raise ValueError("INFER_TARGET_BINDING: target requirements must be a mapping")
    if not isinstance(binding.get("observed", False), bool):
        raise ValueError("INFER_TARGET_BINDING: observed must be boolean")
    if requirements:
        _validate_target_requirements(requirements)
        if binding.get("observed", False):
            capabilities = requirements.get("metadata", {}).get("capabilities")
            if not _supports_write_mode(capabilities, str(binding.get("write_mode", "append"))):
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
        elif name in {"doublequote", "strict"}:
            if not isinstance(value, bool):
                raise ValueError(
                    f"INFER_SOURCE_BINDING: file option {name!r} must be boolean"
                )
        elif name == "null_values" and (
            not isinstance(value, (list, tuple, set, frozenset))
            or not all(
                isinstance(item, (str, int, float, bool)) for item in value
            )
        ):
            raise ValueError(
                "INFER_SOURCE_BINDING: file option 'null_values' must be a sequence"
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
        NormalizedSchema.from_dict(dict(requirements))
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
            raise ValueError(
                f"INFER_SOURCE_UNRESOLVABLE: source file does not exist: {path}"
            )
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
        if resolved.format in {"csv", "tsv"}:
            options = dict(resolved.options)
            if resolved.format == "tsv":
                options.setdefault("delimiter", "\t")
            return read_csv(
                str(resolved.path),
                name=source_name,
                options=options,
                hints=hints,
                limits=limits,
            )
        return read_json(
            str(resolved.path),
            name=source_name,
            lines=resolved.lines or resolved.format == "jsonl",
            hints=hints,
            limits=limits,
        )
    from .facade import from_records

    factory_key = str(binding.get("factory_key") or "")
    factory = source_factory(factory_key)
    return from_records(
        resolved,
        name=name or str(binding.get("identity") or "records"),
        hints=hints,
        limits=limits,
        source_factory=factory,
        source_key=factory_key,
    )
