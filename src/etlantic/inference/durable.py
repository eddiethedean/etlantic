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


def records_binding(identity: str) -> dict[str, Any]:
    return {
        "version": BINDING_VERSION,
        "kind": "records",
        "identity": str(identity),
        "resolver": "registry",
        "factory_key": str(identity),
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
    payload: dict[str, Any] = {
        "version": BINDING_VERSION,
        "kind": "file",
        "format": format,
        "identity": str(identity),
        "uri": str(Path(path).expanduser().resolve()),
        "options": _wire_value(dict(options or {})),
    }
    if lines is not None:
        payload["lines"] = bool(lines)
    return payload


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
        payload = dict(_wire_value(dict(source)))
        if payload.get("version") != BINDING_VERSION:
            raise ValueError("unsupported source binding version")
        return payload
    path = Path(source)
    suffix = path.suffix.lower()
    source_format = format or ("json" if suffix in {".json", ".jsonl"} else suffix.lstrip("."))
    if source_format not in {"csv", "tsv", "json", "jsonl"}:
        raise ValueError(
            f"INFER_SOURCE_UNSUPPORTED: cannot durably bind {source_format!r} source"
        )
    resolved = str(path.expanduser().resolve())
    identity = f"{source_format}:{hashlib.sha256(resolved.encode()).hexdigest()[:20]}"
    return file_binding(source_format, path, identity=identity)


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
        _source_binding_for_rebind(source, format=format) if source is not None else None
    )
    target_payload = (
        dict(_wire_value(dict(target))) if target is not None else None
    )
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


def resolve_source_binding(binding: Mapping[str, Any]) -> Any:
    """Resolve a registered records or local file binding for execution."""
    if not isinstance(binding, Mapping):
        raise ValueError("INFER_SOURCE_BINDING: source binding must be a mapping")
    if int(binding.get("version", 0)) != BINDING_VERSION:
        raise ValueError("INFER_SOURCE_BINDING: unsupported source binding version")
    kind = binding.get("kind")
    if kind == "records" and binding.get("resolver") == "registry":
        key = str(binding.get("factory_key") or "")
        factory = source_factory(key)
        if factory is None:
            raise ValueError(
                f"INFER_SOURCE_UNRESOLVABLE: no source factory registered for {key!r}"
            )
        return factory()
    if kind == "file" and binding.get("format") in {"csv", "tsv", "json", "jsonl"}:
        path = Path(str(binding.get("uri") or ""))
        if not path.is_file():
            raise ValueError(
                f"INFER_SOURCE_UNRESOLVABLE: source file does not exist: {path}"
            )
        return path
    raise ValueError(
        "INFER_SOURCE_UNSUPPORTED: source binding requires an explicit rebind"
    )
