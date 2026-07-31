"""Config validation helpers for connector bindings (stdlib only)."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from etlantic.connectors.errors import ConnectorConfigError

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

_URL_USERINFO_VALUE_RE = re.compile(r"(?i)[a-z][a-z0-9+.-]*://[^/@\s]+:[^/@\s]+@")

_TYPE_MAP: dict[str, type | tuple[type, ...]] = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "object": dict,
    "array": (list, tuple),
    "null": type(None),
}


def is_secret_like_key(key: str) -> bool:
    """Return True when a config key name looks like secret material."""
    key_l = str(key).lower().replace("-", "_")
    if key_l in _STRICT_SECRET_KEYS:
        return True
    return bool(_SECRET_KEY_FRAGMENT_RE.search(key_l))


def reject_secret_like_keys(
    config: Mapping[str, Any],
    *,
    path: str = "config",
    provider: str | None = None,
) -> None:
    """Fail closed when config (nested) contains secret-like keys or URL userinfo."""
    if not isinstance(config, Mapping):
        raise ConnectorConfigError(
            f"{path} must be a mapping",
            code="PMCONN901",
            provider=provider,
        )
    for key, child in config.items():
        key_s = str(key)
        child_path = f"{path}.{key_s}"
        if is_secret_like_key(key_s):
            raise ConnectorConfigError(
                f"{path} contains forbidden secret-like key {key_s!r}",
                code="PMCONN902",
                provider=provider,
                details={"key": key_s, "path": child_path},
            )
        if isinstance(child, Mapping):
            reject_secret_like_keys(child, path=child_path, provider=provider)
        elif isinstance(child, (list, tuple)):
            for index, item in enumerate(child):
                item_path = f"{child_path}[{index}]"
                if isinstance(item, Mapping):
                    reject_secret_like_keys(item, path=item_path, provider=provider)
                elif isinstance(item, str) and _URL_USERINFO_VALUE_RE.search(item):
                    raise ConnectorConfigError(
                        f"{item_path} contains a URL with userinfo credentials",
                        code="PMCONN903",
                        provider=provider,
                    )
        elif isinstance(child, str) and _URL_USERINFO_VALUE_RE.search(child):
            raise ConnectorConfigError(
                f"{child_path} contains a URL with userinfo credentials",
                code="PMCONN903",
                provider=provider,
            )


def validate_config(
    config: Mapping[str, Any] | None,
    schema: Mapping[str, Any],
    *,
    provider: str | None = None,
    path: str = "config",
) -> dict[str, Any]:
    """Validate *config* against a JSON-ish schema dict; reject secret-like keys.

    Supported schema keys (subset): ``type``, ``required``, ``properties``,
    ``additionalProperties``, ``enum``, ``minimum``, ``maximum``, ``minLength``,
    ``maxLength``, ``items``.
    """
    data = dict(config or {})
    reject_secret_like_keys(data, path=path, provider=provider)
    _validate_node(data, schema, path=path, provider=provider)
    return data


def _validate_node(
    value: Any,
    schema: Mapping[str, Any],
    *,
    path: str,
    provider: str | None,
) -> None:
    expected = schema.get("type")
    if expected is not None:
        _check_type(value, expected, path=path, provider=provider)

    if "enum" in schema and value not in schema["enum"]:
        raise ConnectorConfigError(
            f"{path} must be one of {list(schema['enum'])!r}; got {value!r}",
            code="PMCONN904",
            provider=provider,
        )

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise ConnectorConfigError(
                f"{path} must be >= {schema['minimum']}",
                code="PMCONN905",
                provider=provider,
            )
        if "maximum" in schema and value > schema["maximum"]:
            raise ConnectorConfigError(
                f"{path} must be <= {schema['maximum']}",
                code="PMCONN906",
                provider=provider,
            )

    if isinstance(value, str):
        if "minLength" in schema and len(value) < int(schema["minLength"]):
            raise ConnectorConfigError(
                f"{path} length must be >= {schema['minLength']}",
                code="PMCONN907",
                provider=provider,
            )
        if "maxLength" in schema and len(value) > int(schema["maxLength"]):
            raise ConnectorConfigError(
                f"{path} length must be <= {schema['maxLength']}",
                code="PMCONN908",
                provider=provider,
            )

    if isinstance(value, Mapping) and "properties" in schema:
        props = schema["properties"]
        if not isinstance(props, Mapping):
            raise ConnectorConfigError(
                f"{path} schema.properties must be a mapping",
                code="PMCONN909",
                provider=provider,
            )
        required = schema.get("required") or ()
        if not isinstance(required, Sequence) or isinstance(required, (str, bytes)):
            raise ConnectorConfigError(
                f"{path} schema.required must be a sequence of keys",
                code="PMCONN910",
                provider=provider,
            )
        for key in required:
            if key not in value:
                raise ConnectorConfigError(
                    f"{path} missing required key {key!r}",
                    code="PMCONN911",
                    provider=provider,
                )
        additional = schema.get("additionalProperties", True)
        for key, child in value.items():
            key_s = str(key)
            child_schema = props.get(key_s)
            if child_schema is None:
                if additional is False:
                    raise ConnectorConfigError(
                        f"{path} has unexpected key {key_s!r}",
                        code="PMCONN912",
                        provider=provider,
                    )
                if isinstance(additional, Mapping):
                    _validate_node(
                        child,
                        additional,
                        path=f"{path}.{key_s}",
                        provider=provider,
                    )
                continue
            if isinstance(child_schema, Mapping):
                _validate_node(
                    child,
                    child_schema,
                    path=f"{path}.{key_s}",
                    provider=provider,
                )

    if isinstance(value, (list, tuple)) and "items" in schema:
        item_schema = schema["items"]
        if isinstance(item_schema, Mapping):
            for index, item in enumerate(value):
                _validate_node(
                    item,
                    item_schema,
                    path=f"{path}[{index}]",
                    provider=provider,
                )


def _check_type(
    value: Any,
    expected: str | Sequence[str],
    *,
    path: str,
    provider: str | None,
) -> None:
    names: list[str]
    if isinstance(expected, str):
        names = [expected]
    elif isinstance(expected, Sequence):
        names = [str(x) for x in expected]
    else:
        raise ConnectorConfigError(
            f"{path} schema.type must be a string or list of strings",
            code="PMCONN913",
            provider=provider,
        )
    for name in names:
        py = _TYPE_MAP.get(name)
        if py is None:
            raise ConnectorConfigError(
                f"{path} schema.type {name!r} is unsupported",
                code="PMCONN914",
                provider=provider,
            )
        # bool is a subclass of int; never accept it for integer/number.
        if name in {"integer", "number"} and isinstance(value, bool):
            continue
        if isinstance(value, py):
            return
    raise ConnectorConfigError(
        f"{path} must be type {names!r}; got {type(value).__name__}",
        code="PMCONN915",
        provider=provider,
    )


__all__ = [
    "is_secret_like_key",
    "reject_secret_like_keys",
    "validate_config",
]
