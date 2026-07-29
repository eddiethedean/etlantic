"""Extension metadata namespaces and size budgets.

Plugin and core extension keys should use a reserved prefix so plan, profile,
and report metadata remain evolvable without opening every core schema.
"""

from __future__ import annotations

import json
import re
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


def facade_provenance(
    *,
    identity: str,
    version: str | None = None,
) -> dict[str, Any]:
    """Return standard provenance for a domain facade package.

    Facades stamp ``kind="facade"`` plus ``identity`` (package name) so
    ``PipelineDefinition.provenance`` attributes definitions without putting
    domain vocabulary into core wire schemas.
    """
    payload: dict[str, Any] = {"kind": "facade", "identity": str(identity)}
    if version is not None:
        payload["version"] = str(version)
    return payload


def namespaced_extension_items(
    mapping: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return only keys that use reserved extension namespaces or core keys."""
    if not mapping:
        return {}
    return {str(k): v for k, v in mapping.items() if _is_namespaced(k)}


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

    # Secret-like keys are always rejected (plans/reports/profiles must stay
    # secret-free). Namespace strictness remains opt-in via ``strict``.
    _reject_nested_secret_material(metadata, path=path)

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


_STRICT_SECRET_KEYS = frozenset(
    {
        "password",
        "passwd",
        "pwd",
        "secret",
        "secret_value",
        "token",
        "api_key",
        "api_token",
        "access_key",
        "access_token",
        "authorization",
        "aws_secret_access_key",
        "aws_access_key_id",
        "private_key",
        "client_secret",
        "credential",
        "credentials",
        "dsn",
        "connection_string",
        "jdbc_url",
        "database_url",
        "db_url",
    }
)

_SECRET_KEY_FRAGMENT_RE = re.compile(
    r"(^|_)(password|passwd|pwd|secret_value|token|api_key|api_token|"
    r"access_key|access_token|private_key|client_secret|credential|"
    r"credentials|authorization|dsn|connection_string|jdbc_url|"
    r"database_url|db_url|secret)$",
    re.IGNORECASE,
)

_URL_USERINFO_VALUE_RE = re.compile(
    r"(?i)[a-z][a-z0-9+.-]*://[^/@\s]+:[^/@\s]+@"
)


def _is_secret_like_key(key: str) -> bool:
    key_l = str(key).lower().replace("-", "_")
    if key_l in _STRICT_SECRET_KEYS:
        return True
    return bool(_SECRET_KEY_FRAGMENT_RE.search(key_l))


def _reject_nested_secret_material(value: Any, *, path: str) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if _is_secret_like_key(str(key)):
                raise ValueError(
                    f"{path} contains forbidden secret-like key {key!r}; "
                    "failing closed under strict production metadata."
                )
            _reject_nested_secret_material(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_nested_secret_material(item, path=f"{path}[{index}]")
    elif isinstance(value, str) and _URL_USERINFO_VALUE_RE.search(value):
        raise ValueError(
            f"{path} contains a URL with userinfo credentials; "
            "failing closed under strict production metadata."
        )
