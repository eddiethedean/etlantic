"""Extension metadata namespaces and size budgets.

Plugin and core extension keys should use a reserved prefix so plan, profile,
and report metadata remain evolvable without opening every core schema.
"""

from __future__ import annotations

import json
import warnings
from typing import Any

EXTENSION_NAMESPACE_PREFIXES: tuple[str, ...] = ("etlantic.", "plugin:")
MAX_METADATA_BYTES = 256 * 1024
MAX_METADATA_DEPTH = 8

# First-party plan/profile wire keys (not plugin extensions).
CORE_METADATA_KEYS: frozenset[str] = frozenset(
    {
        "capabilities",
        "collection_points",
        "conversion_boundaries",
        "dataframe_protocol",
        "engine",
        "interchange",
        "lazy_supported",
        "ownership",
        "planner",
        "planner_version",
        "plugin_trust_records",
        "plugin_version",
        "region",
        "region_engine",
        "spark_fusion",
        "spark_protocol",
        "spark_streaming_stability",
        "sql_fusion",
        "sql_protocol",
        "streaming",
        "validation_policy",
    }
)


def _max_depth(value: Any) -> int:
    """Return nesting depth for mappings and sequences (leaves are 0)."""
    if isinstance(value, dict):
        if not value:
            return 1
        return 1 + max(_max_depth(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        if not value:
            return 1
        return 1 + max(_max_depth(v) for v in value)
    return 0


def _is_namespaced(key: object) -> bool:
    text = str(key)
    if text in CORE_METADATA_KEYS:
        return True
    return any(text.startswith(prefix) for prefix in EXTENSION_NAMESPACE_PREFIXES)


def validate_extension_metadata(
    metadata: dict[str, Any],
    *,
    path: str = "metadata",
    strict: bool = False,
) -> None:
    """Validate extension metadata size, depth, and optional namespaces.

    Always enforces JSON-serializability, :data:`MAX_METADATA_BYTES`, and
    :data:`MAX_METADATA_DEPTH`. Bare (non-namespaced) top-level keys warn when
    ``strict=False`` (default, so existing metadata still loads) and raise
    :class:`ValueError` when ``strict=True``.
    """
    if not isinstance(metadata, dict):
        raise TypeError(f"{path} must be a mapping, got {type(metadata)!r}")

    depth = _max_depth(metadata)
    if depth > MAX_METADATA_DEPTH:
        raise ValueError(
            f"{path} exceeds max nesting depth {MAX_METADATA_DEPTH} "
            f"(got depth {depth})."
        )

    try:
        payload = json.dumps(metadata, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{path} must be JSON-serializable: {exc}") from exc
    size = len(payload.encode("utf-8"))
    if size > MAX_METADATA_BYTES:
        raise ValueError(
            f"{path} exceeds size budget of {MAX_METADATA_BYTES} bytes "
            f"(got {size} bytes)."
        )

    bare = sorted(str(key) for key in metadata if not _is_namespaced(key))
    if not bare:
        return
    message = (
        f"{path} keys should use extension namespaces "
        f"{EXTENSION_NAMESPACE_PREFIXES}; got bare keys: {bare!r}"
    )
    if strict:
        raise ValueError(message)
    warnings.warn(message, UserWarning, stacklevel=2)
