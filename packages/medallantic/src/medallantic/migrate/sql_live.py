"""Live SqlPipelineBuilder → secret-free IR extraction.

SqlPipelineBuilder / Moltres are **optional** dependencies. When they are not
installed, callers should use frozen IR fixtures via
:func:`medallantic.adapt.adapt_pipeline`. This module never embeds secrets or
source rows.
"""

from __future__ import annotations

from typing import Any

from etlantic.diagnostics import Diagnostic, Severity
from medallantic.ir import (
    LayerKind,
    SparkForgePipelineSpec,
    StepKind,
)
from medallantic.moltres_rules import is_moltres_rule_entry

_SECRET_KEY_FRAGMENTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "credential",
    "api_key",
    "apikey",
    "access_key",
    "private_key",
    "auth",
    "jdbc_url",
    "connection_string",
    "connection_uri",
    "dsn",
    "jdbc",
)


class LiveBridgeError(Exception):
    """Raised when a live SqlPipelineBuilder cannot be extracted."""

    def __init__(
        self,
        message: str,
        *,
        diagnostics: list[Diagnostic] | None = None,
        code: str = "PMSQ350",
    ) -> None:
        super().__init__(message)
        self.diagnostics = list(diagnostics or [])
        self.code = code


def sql_pipeline_builder_available() -> bool:
    """Return True when a SQL pipeline builder module can be imported."""
    try:
        import importlib

        for mod in (
            "sql_pipeline_builder",
            "moltres.pipeline_builder",
            "moltres.sql_pipeline_builder",
        ):
            try:
                importlib.import_module(mod)
                return True
            except ImportError:
                continue
        return False
    except ImportError:
        return False


def from_sql_pipeline_builder(
    builder: Any,
    *,
    name: str | None = None,
    engine: str = "sql",
) -> tuple[SparkForgePipelineSpec, list[Diagnostic]]:
    """Extract a secret-free ``SparkForgePipelineSpec`` from a live SQL builder.

    Accepts:
    - objects with ``steps`` / ``to_dict`` / ``export`` attributes
    - SQLAlchemy Select-like objects
    - plain mappings already shaped like IR
    """
    diagnostics: list[Diagnostic] = []
    if isinstance(builder, SparkForgePipelineSpec):
        return builder, diagnostics
    if isinstance(builder, dict):
        cleaned = _sanitize_mapping(dict(builder), diagnostics=diagnostics, path=())
        cleaned.setdefault("engine", engine)
        spec, parse_diags = SparkForgePipelineSpec.parse(cleaned)
        diagnostics.extend(parse_diags)
        return spec, diagnostics

    data = _builder_to_mapping(builder, diagnostics=diagnostics)
    if name:
        data["name"] = name
    data.setdefault("engine", engine)
    spec, parse_diags = SparkForgePipelineSpec.parse(data)
    diagnostics.extend(parse_diags)
    if any(d.severity is Severity.ERROR for d in diagnostics):
        raise LiveBridgeError(
            "Live SqlPipelineBuilder extraction failed.",
            diagnostics=diagnostics,
            code="PMSQ350",
        )
    return spec, diagnostics


def _builder_to_mapping(
    builder: Any,
    *,
    diagnostics: list[Diagnostic],
) -> dict[str, Any]:
    for attr in ("to_secret_free_dict", "to_ir", "export_ir", "to_dict", "as_dict"):
        fn = getattr(builder, attr, None)
        if callable(fn):
            raw = fn()
            if isinstance(raw, dict):
                return _sanitize_mapping(raw, diagnostics=diagnostics, path=())

    if _looks_like_sqlalchemy_select(builder):
        return _select_to_mapping(builder, diagnostics=diagnostics)

    name = str(
        getattr(builder, "name", None)
        or getattr(builder, "pipeline_name", None)
        or type(builder).__name__
    )
    schema = str(
        getattr(builder, "schema", None)
        or getattr(builder, "db_schema", None)
        or "default"
    )
    steps_raw = (
        getattr(builder, "steps", None)
        or getattr(builder, "_steps", None)
        or getattr(builder, "layers", None)
        or ()
    )
    steps: list[dict[str, Any]] = []
    if isinstance(steps_raw, dict):
        iterable = list(steps_raw.values())
    else:
        iterable = list(steps_raw)
    for index, step in enumerate(iterable):
        extracted = _extract_step(step, index=index, diagnostics=diagnostics)
        if extracted is not None:
            steps.append(extracted)

    metadata: dict[str, Any] = {}
    meta_attr = getattr(builder, "metadata", None)
    if isinstance(meta_attr, dict):
        metadata.update(
            _scrub_mapping(
                meta_attr,
                diagnostics=diagnostics,
                path=("metadata",),
            )
        )
    orm_models = getattr(builder, "models", None) or getattr(
        builder, "orm_models", None
    )
    if orm_models:
        metadata["orm_models"] = [
            getattr(m, "__name__", type(m).__name__) for m in list(orm_models)
        ]

    return {
        "name": name,
        "schema": schema,
        "engine": str(getattr(builder, "engine", None) or "sql"),
        "min_bronze_rate": float(getattr(builder, "min_bronze_rate", 90.0) or 90.0),
        "min_silver_rate": float(getattr(builder, "min_silver_rate", 95.0) or 95.0),
        "min_gold_rate": float(getattr(builder, "min_gold_rate", 98.0) or 98.0),
        "steps": steps,
        "metadata": metadata,
        "legacy_engine_extensions": list(
            getattr(builder, "legacy_engine_extensions", None) or ()
        ),
    }


def _extract_step(
    step: Any,
    *,
    index: int,
    diagnostics: list[Diagnostic],
) -> dict[str, Any] | None:
    if isinstance(step, dict):
        return _sanitize_step_dict(step, diagnostics=diagnostics, index=index)
    name = getattr(step, "name", None)
    if name is None or not str(name).strip():
        diagnostics.append(
            Diagnostic(
                code="PMSQ310",
                severity=Severity.ERROR,
                message=f"Live SQL builder step at index {index} is missing a name.",
                path=("steps", str(index), "name"),
                phase="sql_live",
            )
        )
        return None
    layer = str(getattr(step, "layer", None) or "bronze").lower()
    kind = str(getattr(step, "kind", None) or _kind_for_layer(layer))
    rules = _normalize_rules(getattr(step, "rules", None) or {})
    transform_ref = getattr(step, "transform_ref", None) or getattr(
        step, "transform", None
    )
    if callable(transform_ref) and not isinstance(transform_ref, (str, type)):
        transform_ref = (
            f"{transform_ref.__module__}:"
            f"{getattr(transform_ref, '__qualname__', transform_ref.__name__)}"
        )
    step_meta = _scrub_mapping(
        dict(getattr(step, "metadata", None) or {}),
        diagnostics=diagnostics,
        path=("steps", str(name), "metadata"),
    )
    return {
        "name": str(name),
        "kind": kind,
        "layer": layer,
        "source": getattr(step, "source", None),
        "table_name": getattr(step, "table_name", None)
        or getattr(step, "table", None)
        or getattr(step, "asset", None),
        "transform_ref": str(transform_ref) if transform_ref is not None else None,
        "rules": rules,
        "write_mode": getattr(step, "write_mode", None),
        "metadata": step_meta,
    }


def _normalize_rules(rules: Any) -> dict[str, Any]:
    if not isinstance(rules, dict):
        return {}
    out: dict[str, Any] = {}
    for field, entries in rules.items():
        items = list(entries) if isinstance(entries, (list, tuple)) else [entries]
        normalized: list[Any] = []
        for item in items:
            if isinstance(item, (str, dict)):
                normalized.append(item)
            elif is_moltres_rule_entry(item):
                normalized.append(
                    {
                        "kind": "moltres_expr",
                        "metadata": {
                            "expr_type": type(item).__name__,
                            "expr_module": type(item).__module__,
                        },
                    }
                )
            elif callable(item) and not isinstance(item, type):
                normalized.append(
                    {
                        "kind": "moltres_callable",
                        "expr_ref": (
                            f"{item.__module__}:"
                            f"{getattr(item, '__qualname__', getattr(item, '__name__', 'fn'))}"
                        ),
                        "metadata": {"callable_type": type(item).__name__},
                    }
                )
            else:
                normalized.append(str(item))
        out[str(field)] = normalized
    return out


def _is_secret_key(key: str) -> bool:
    key_l = str(key).lower()
    if key_l in {
        "url",
        "uri",
        "dsn",
        "jdbc_url",
        "connection_string",
        "connection_uri",
    }:
        return True
    return any(fragment in key_l for fragment in _SECRET_KEY_FRAGMENTS)


def _scrub_value(value: Any) -> Any:
    from etlantic.runtime.logging import redact_message

    if isinstance(value, list):
        return [_scrub_value(v) for v in value]
    if isinstance(value, str):
        return redact_message(value)
    return value


def _scrub_mapping(
    data: dict[str, Any],
    *,
    diagnostics: list[Diagnostic],
    path: tuple[str, ...],
) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in data.items():
        key_s = str(key)
        if _is_secret_key(key_s):
            diagnostics.append(
                Diagnostic(
                    code="PMSQ351",
                    severity=Severity.WARNING,
                    message=f"Omitting secret-like key {key_s!r} from IR.",
                    path=(*path, key_s),
                    phase="sparkforge_live",
                )
            )
            continue
        if isinstance(value, dict):
            cleaned[key_s] = _scrub_mapping(
                value,
                diagnostics=diagnostics,
                path=(*path, key_s),
            )
        else:
            cleaned[key_s] = _scrub_value(value)
    return cleaned


def _sanitize_mapping(
    data: dict[str, Any],
    *,
    diagnostics: list[Diagnostic],
    path: tuple[str, ...],
) -> dict[str, Any]:
    cleaned = _scrub_mapping(data, diagnostics=diagnostics, path=path)
    steps = cleaned.get("steps")
    if isinstance(steps, list):
        cleaned["steps"] = [
            _sanitize_step_dict(step, diagnostics=diagnostics, index=i)
            if isinstance(step, dict)
            else step
            for i, step in enumerate(steps)
        ]
    return cleaned


def _sanitize_step_dict(
    step: dict[str, Any],
    *,
    diagnostics: list[Diagnostic],
    index: int = 0,
) -> dict[str, Any]:
    name = str(step.get("name") or index)
    out = _scrub_mapping(dict(step), diagnostics=diagnostics, path=("steps", name))
    if "rules" in step:
        out["rules"] = _normalize_rules(step.get("rules") or {})
    return out


def _looks_like_sqlalchemy_select(obj: Any) -> bool:
    module = type(obj).__module__ or ""
    name = type(obj).__name__
    if "sqlalchemy" in module and name in {
        "Select",
        "CompoundSelect",
        "GenerativeSelect",
    }:
        return True
    return hasattr(obj, "selected_columns") and hasattr(obj, "froms")


def _select_to_mapping(
    select_obj: Any,
    *,
    diagnostics: list[Diagnostic],
) -> dict[str, Any]:
    _ = diagnostics
    return {
        "name": "sqlalchemy_select",
        "schema": "default",
        "engine": "sql",
        "min_bronze_rate": 90.0,
        "min_silver_rate": 95.0,
        "min_gold_rate": 98.0,
        "steps": [
            {
                "name": "select_source",
                "kind": StepKind.BRONZE_RULES.value,
                "layer": "bronze",
                "table_name": "select_source",
                "metadata": {
                    "source_kind": "sqlalchemy_select",
                    "select_type": type(select_obj).__name__,
                },
            }
        ],
        "metadata": {"source_kind": "sqlalchemy_select"},
        "legacy_engine_extensions": [],
    }


def _kind_for_layer(layer: str) -> str:
    if layer == LayerKind.BRONZE.value or layer == "bronze":
        return StepKind.BRONZE_RULES.value
    if layer == LayerKind.SILVER.value or layer == "silver":
        return StepKind.SILVER_TRANSFORM.value
    if layer == LayerKind.GOLD.value or layer == "gold":
        return StepKind.GOLD_TRANSFORM.value
    return StepKind.UNKNOWN.value
