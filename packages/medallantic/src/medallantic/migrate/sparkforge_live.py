"""Live SparkForge ``PipelineBuilder`` → secret-free IR extraction.

SparkForge is an **optional** dependency. When it is not installed, callers
should use frozen IR fixtures via :func:`medallantic.adapt.adapt_pipeline`.
This module never embeds secrets or source rows.
"""

from __future__ import annotations

from typing import Any

from etlantic.diagnostics import Diagnostic, Severity
from medallantic.column_rules import is_native_rule_entry
from medallantic.ir import (
    LayerKind,
    SparkForgePipelineSpec,
    StepKind,
)

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
)


class LiveBridgeError(Exception):
    """Raised when a live PipelineBuilder cannot be extracted."""

    def __init__(
        self,
        message: str,
        *,
        diagnostics: list[Diagnostic] | None = None,
        code: str = "PMSF350",
    ) -> None:
        super().__init__(message)
        self.diagnostics = list(diagnostics or [])
        self.code = code


def sparkforge_available() -> bool:
    """Return True when a SparkForge pipeline_builder module can be imported."""
    try:
        import importlib

        importlib.import_module("sparkforge.pipeline_builder")
        return True
    except ImportError:
        return False


def from_pipeline_builder(
    builder: Any,
    *,
    name: str | None = None,
    engine: str = "spark",
) -> tuple[SparkForgePipelineSpec, list[Diagnostic]]:
    """Extract a secret-free ``SparkForgePipelineSpec`` from a live builder.

    Accepts:
    - objects with ``steps`` / ``to_dict`` / ``export`` attributes (SparkForge)
    - plain mappings already shaped like IR
    """
    diagnostics: list[Diagnostic] = []
    if isinstance(builder, SparkForgePipelineSpec):
        return builder, diagnostics
    if isinstance(builder, dict):
        cleaned = _sanitize_mapping(dict(builder), diagnostics=diagnostics, path=())
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
            "Live PipelineBuilder extraction failed.",
            diagnostics=diagnostics,
            code="PMSF350",
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
    delta_ops = getattr(builder, "delta_operations", None) or getattr(
        builder, "delta_ops", None
    )
    if delta_ops:
        metadata["delta_operations"] = [str(x) for x in list(delta_ops)]
    meta_attr = getattr(builder, "metadata", None)
    if isinstance(meta_attr, dict):
        metadata.update(
            _scrub_mapping(
                meta_attr,
                diagnostics=diagnostics,
                path=("metadata",),
            )
        )

    return {
        "name": name,
        "schema": schema,
        "engine": str(getattr(builder, "engine", None) or "spark"),
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
                code="PMSF310",
                severity=Severity.ERROR,
                message=f"Live builder step at index {index} is missing a name.",
                path=("steps", str(index), "name"),
                phase="sparkforge_live",
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
            elif callable(item) and not isinstance(item, type):
                normalized.append(
                    {
                        "kind": "pyspark_callable",
                        "expr_ref": (
                            f"{item.__module__}:"
                            f"{getattr(item, '__qualname__', getattr(item, '__name__', 'fn'))}"
                        ),
                        "metadata": {"callable_type": type(item).__name__},
                    }
                )
            elif is_native_rule_entry(item):
                normalized.append(
                    {
                        "kind": "pyspark_column",
                        "metadata": {
                            "column_type": type(item).__name__,
                            "column_module": type(item).__module__,
                        },
                    }
                )
            else:
                normalized.append(str(item))
        out[str(field)] = normalized
    return out


def _is_secret_key(key: str) -> bool:
    key_l = str(key).lower()
    return any(fragment in key_l for fragment in _SECRET_KEY_FRAGMENTS)


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
                    code="PMSF351",
                    severity=Severity.WARNING,
                    message=f"Omitting secret-like metadata key {key_s!r} from IR.",
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
            cleaned[key_s] = value
    return cleaned


def _sanitize_mapping(
    data: dict[str, Any],
    *,
    diagnostics: list[Diagnostic],
    path: tuple[str, ...],
) -> dict[str, Any]:
    cleaned = dict(data)
    meta = cleaned.get("metadata")
    if isinstance(meta, dict):
        cleaned["metadata"] = _scrub_mapping(
            meta,
            diagnostics=diagnostics,
            path=(*path, "metadata"),
        )
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
    out = dict(step)
    name = str(out.get("name") or index)
    if "rules" in out:
        out["rules"] = _normalize_rules(out.get("rules") or {})
    meta = out.get("metadata")
    if isinstance(meta, dict):
        out["metadata"] = _scrub_mapping(
            meta,
            diagnostics=diagnostics,
            path=("steps", name, "metadata"),
        )
    return out


def _kind_for_layer(layer: str) -> str:
    if layer == LayerKind.BRONZE.value or layer == "bronze":
        return StepKind.BRONZE_RULES.value
    if layer == LayerKind.SILVER.value or layer == "silver":
        return StepKind.SILVER_TRANSFORM.value
    if layer == LayerKind.GOLD.value or layer == "gold":
        return StepKind.GOLD_TRANSFORM.value
    return StepKind.UNKNOWN.value
