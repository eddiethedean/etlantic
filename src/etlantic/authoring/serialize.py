"""Canonical serialization and fingerprinting for PipelineDefinition."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from etlantic.authoring.definition import PIPELINE_SCHEMA, PipelineDefinition
from etlantic.authoring.upgrade import (
    UnsupportedPipelineSchemaError,
    upgrade_pipeline_dict,
)
from etlantic.extensions import validate_extension_metadata
from etlantic.interchange.security import DEFAULT_MAX_BYTES, read_text_bounded
from etlantic.plan.freeze import mutable_copy


def _validate_definition_extension_bags(
    defn: PipelineDefinition,
    *,
    strict: bool = False,
) -> None:
    """Validate definition / node extension bags for size, depth, and namespaces."""
    validate_extension_metadata(
        mutable_copy(defn.extensions), path="extensions", strict=strict
    )
    validate_extension_metadata(
        mutable_copy(defn.metadata), path="metadata", strict=strict
    )
    for node in defn.nodes:
        validate_extension_metadata(
            mutable_copy(node.metadata),
            path=f"nodes.{node.name}.metadata",
            strict=strict,
        )
    for contract in defn.contracts:
        validate_extension_metadata(
            mutable_copy(contract.metadata),
            path=f"contracts.{contract.identity}.metadata",
            strict=strict,
        )


_FORBIDDEN_KEYS = frozenset(
    {
        "__import__",
        "__class__",
        "callable",
        "pickle",
        "bytecode",
        "secret_value",
        "password",
        "token",
        "resolved_secret",
        "api_token",
        "access_key",
        "access_token",
        "private_key",
        "client_secret",
        "api_key",
        "passwd",
        "pwd",
        "credential",
        "credentials",
        "authorization",
        "aws_secret_access_key",
        "aws_access_key_id",
    }
)
_SECRET_REF_ALLOWED = frozenset({"provider", "name"})
# Nested plaintext material that must never appear under any key (except
# parameter ``value`` / ``default``, which are ordinary authoring fields).
_NESTED_SECRET_MATERIAL = frozenset(
    {
        "token",
        "password",
        "secret",
        "secret_value",
        "resolved_secret",
        "api_key",
        "api_token",
        "access_key",
        "access_token",
        "private_key",
        "client_secret",
        "passwd",
        "pwd",
        "credential",
        "credentials",
        "authorization",
        "aws_secret_access_key",
        "aws_access_key_id",
    }
)

_MAX_DEPTH = 64
_MAX_COLLECTION = 10_000


def _sort_structure(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _sort_structure(value[k]) for k in sorted(value)}
    if isinstance(value, list):
        return [_sort_structure(v) for v in value]
    return value


def _reject_forbidden(value: Any, *, path: str = "$") -> None:
    if isinstance(value, dict):
        if len(value) > _MAX_COLLECTION:
            raise ValueError(
                f"Pipeline definition mapping at {path} exceeds collection budget"
            )
        for key, child in value.items():
            key_s = str(key)
            lowered = key_s.lower()
            if key_s in _FORBIDDEN_KEYS or lowered in _FORBIDDEN_KEYS:
                raise ValueError(
                    f"Pipeline definition rejects forbidden field {key_s!r} at {path}"
                )
            if key_s == "secret_ref":
                if not isinstance(child, dict):
                    raise ValueError(
                        f"Pipeline definition rejects non-object secret_ref at {path}"
                    )
                extra = set(child) - _SECRET_REF_ALLOWED
                if extra:
                    raise ValueError(
                        f"Pipeline definition rejects secret_ref fields "
                        f"{sorted(extra)!r} at {path}.{key_s} "
                        f"(only provider/name allowed)"
                    )
                if "provider" not in child or "name" not in child:
                    raise ValueError(
                        f"Pipeline definition secret_ref at {path}.{key_s} "
                        f"requires provider and name"
                    )
                continue
            if lowered in {"has_secret_ref", "secret_provider"}:
                _reject_forbidden(child, path=f"{path}.{key_s}")
                continue
            if "secret" in lowered or lowered in _NESTED_SECRET_MATERIAL:
                raise ValueError(
                    f"Pipeline definition rejects secret payload at {path}.{key_s}"
                )
            if isinstance(child, dict):
                bad = [
                    str(k) for k in child if str(k).lower() in _NESTED_SECRET_MATERIAL
                ]
                if bad:
                    raise ValueError(
                        f"Pipeline definition rejects secret value fields "
                        f"{bad!r} at {path}.{key_s}"
                    )
            _reject_forbidden(child, path=f"{path}.{key_s}")
    elif isinstance(value, list):
        if len(value) > _MAX_COLLECTION:
            raise ValueError(
                f"Pipeline definition list at {path} exceeds collection budget"
            )
        for idx, child in enumerate(value):
            _reject_forbidden(child, path=f"{path}[{idx}]")


def _check_depth(value: Any, *, depth: int = 0) -> None:
    if depth > _MAX_DEPTH:
        raise ValueError("Pipeline definition exceeds nesting depth budget")
    if isinstance(value, dict):
        for child in value.values():
            _check_depth(child, depth=depth + 1)
    elif isinstance(value, list):
        for child in value:
            _check_depth(child, depth=depth + 1)


def canonical_pipeline_dict(defn: PipelineDefinition) -> dict[str, Any]:
    """Return a deterministically ordered definition dict for hashing."""
    data = copy.deepcopy(defn.to_dict())
    data.pop("fingerprint", None)
    return _sort_structure(data)


def canonical_pipeline_json(defn: PipelineDefinition) -> str:
    """Return canonical JSON as a UTF-8 string."""
    return json.dumps(
        canonical_pipeline_dict(defn),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def pipeline_fingerprint(defn: PipelineDefinition) -> str:
    """Compute a stable SHA-256 fingerprint of the canonical definition.

    Args:
        defn: Pipeline definition to hash (fingerprint field is ignored in the
            canonical payload).

    Returns:
        Hex-encoded SHA-256 digest of the canonical JSON form.
    """
    payload = canonical_pipeline_json(defn).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def pipeline_to_dict(
    defn: PipelineDefinition, *, with_fingerprint: bool = True
) -> dict[str, Any]:
    """Serialize a definition, optionally embedding its fingerprint.

    Args:
        defn: Definition to serialize.
        with_fingerprint: When True, set ``fingerprint`` to the recomputed
            digest (recommended for interchange).

    Returns:
        A JSON-friendly mapping suitable for ``pipeline_from_dict``.
    """
    _validate_definition_extension_bags(defn, strict=False)
    data = defn.to_dict()
    if with_fingerprint:
        data["fingerprint"] = pipeline_fingerprint(defn)
    return data


def pipeline_to_json(
    defn: PipelineDefinition,
    *,
    indent: int | None = 2,
    with_fingerprint: bool = True,
) -> str:
    """Serialize a definition to JSON text.

    Args:
        defn: Definition to serialize.
        indent: Pretty-print indent, or ``None`` for compact canonical JSON.
        with_fingerprint: Forwarded to ``pipeline_to_dict``.

    Returns:
        UTF-8 JSON text (trailing newline when ``indent`` is not ``None``).
    """
    data = pipeline_to_dict(defn, with_fingerprint=with_fingerprint)
    if indent is None:
        return json.dumps(
            data, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
    return json.dumps(data, indent=indent, sort_keys=True, ensure_ascii=False) + "\n"


def verify_pipeline_fingerprint(defn: PipelineDefinition) -> None:
    """Recompute fingerprint and compare to ``defn.fingerprint``.

    Args:
        defn: Definition whose embedded fingerprint must match.

    Returns:
        None.

    Raises:
        ValueError: If the embedded fingerprint does not match the recomputed
            digest.
    """
    expected = pipeline_fingerprint(defn)
    if defn.fingerprint != expected:
        raise ValueError(
            f"PipelineDefinition fingerprint mismatch: "
            f"embedded={defn.fingerprint!r} computed={expected!r}"
        )


def pipeline_from_dict(
    data: dict[str, Any],
    *,
    verify: bool = True,
) -> PipelineDefinition:
    """Deserialize a definition from a mapping.

    Args:
        data: ``etlantic.pipeline/1`` document (may be upgraded from prior
            minors via the codec upgrade path).
        verify: When True, require a matching fingerprint and supported schema.

    Returns:
        An immutable ``PipelineDefinition``.

    Raises:
        TypeError: If ``data`` is not a mapping.
        ValueError: If forbidden keys, fingerprint mismatch, or missing
            fingerprint when ``verify=True``.
        UnsupportedPipelineSchemaError: If the schema is unsupported after
            upgrade when ``verify=True``.
    """
    if not isinstance(data, dict):
        raise TypeError(
            f"PipelineDefinition document must be a mapping, got {type(data)!r}"
        )
    _check_depth(data)
    _reject_forbidden(data)
    upgraded = upgrade_pipeline_dict(mutable_copy(data))
    defn = PipelineDefinition.from_dict(upgraded)
    _validate_definition_extension_bags(defn, strict=False)
    if verify:
        if defn.schema != PIPELINE_SCHEMA:
            raise UnsupportedPipelineSchemaError(
                f"Unsupported PipelineDefinition schema {defn.schema!r}"
            )
        expected = pipeline_fingerprint(defn)
        if defn.fingerprint is None:
            raise ValueError(
                "PipelineDefinition fingerprint required when verify=True "
                "(seal via write_pipeline_json / with_fingerprint)"
            )
        if defn.fingerprint != expected:
            raise ValueError(
                f"PipelineDefinition fingerprint mismatch: "
                f"embedded={defn.fingerprint!r} computed={expected!r}"
            )
    return defn


def pipeline_from_json(text: str, *, verify: bool = True) -> PipelineDefinition:
    """Deserialize a definition from JSON text (inert — no imports or I/O).

    Args:
        text: JSON document text.
        verify: Forwarded to ``pipeline_from_dict``.

    Returns:
        An immutable ``PipelineDefinition``.

    Raises:
        ValueError: If the payload exceeds size budget, is invalid JSON, or
            is not a JSON object.
    """
    if len(text.encode("utf-8")) > DEFAULT_MAX_BYTES:
        raise ValueError("Pipeline definition JSON exceeds read budget")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid PipelineDefinition JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("PipelineDefinition JSON must be an object")
    return pipeline_from_dict(data, verify=verify)


def write_pipeline_json(
    defn: PipelineDefinition,
    path: str | Path,
    *,
    indent: int | None = 2,
) -> Path:
    """Write canonical definition JSON to ``path``.

    Args:
        defn: Definition to write (fingerprint is embedded).
        path: Destination file path.
        indent: Pretty-print indent, or ``None`` for compact JSON.

    Returns:
        The resolved ``Path`` written.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(pipeline_to_json(defn, indent=indent), encoding="utf-8")
    return target


def read_pipeline_json(
    path: str | Path,
    *,
    verify: bool = True,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> PipelineDefinition:
    """Read a definition JSON document from disk under Safe I/O budgets.

    Args:
        path: Path to an ``etlantic.pipeline/1`` JSON file.
        verify: Forwarded to ``pipeline_from_json``.
        max_bytes: Maximum bytes to read (Safe I/O budget).

    Returns:
        An immutable ``PipelineDefinition``.

    Raises:
        ValueError: On size, JSON, fingerprint, or schema failures.
        OSError: If the file cannot be read.
    """
    _resolved, text = read_text_bounded(path, max_bytes=max_bytes)
    return pipeline_from_json(text, verify=verify)
