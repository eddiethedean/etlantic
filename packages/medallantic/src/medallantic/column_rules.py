"""Non-portable PySpark Column / callable quality rules (Medallantic-only).

These rules are **not** part of ``etlantic.quality/1``. They require the
``quality.pyspark_column`` engine capability and fail closed with ``MDL130``
when the selected engine cannot execute them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


NATIVE_RULE_KINDS = frozenset(
    {
        "pyspark_column",
        "spark_column",
        "column",
        "column_expr",
        "pyspark_callable",
    }
)

NATIVE_QUALITY_CAPABILITY = "quality.pyspark_column"


@dataclass(frozen=True, slots=True)
class NativeColumnRule:
    """One engine-native Column / callable validator (secret-free metadata)."""

    field: str
    kind: str
    expr_ref: str | None = None
    required: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "kind": self.kind,
            "expr_ref": self.expr_ref,
            "required": self.required,
            "metadata": dict(self.metadata),
        }


def is_native_rule_entry(item: Any) -> bool:
    """Return True when a rule entry is a PySpark Column / native callable."""
    if isinstance(item, dict):
        kind = str(item.get("kind") or item.get("type") or "").strip().lower()
        return kind in NATIVE_RULE_KINDS
    type_name = type(item).__name__
    module = type(item).__module__ or ""
    if "Column" in type_name and ("pyspark" in module or "sparkless" in module):
        return True
    if callable(item) and not isinstance(item, (str, bytes, dict, list, tuple, type)):
        # Bare callables in rules are treated as native validators (not classes).
        return True
    return False


def split_portable_and_native_rules(
    rules: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[NativeColumnRule]]:
    """Partition a rules mapping into portable shorthand and native Column rules."""
    if not rules:
        return {}, []
    portable: dict[str, Any] = {}
    native: list[NativeColumnRule] = []
    for field, entries in rules.items():
        field_name = str(field)
        items = list(entries) if isinstance(entries, (list, tuple)) else [entries]
        portable_items: list[Any] = []
        for item in items:
            if is_native_rule_entry(item):
                native.append(_to_native(field_name, item))
            else:
                portable_items.append(item)
        if portable_items:
            portable[field_name] = portable_items
    return portable, native


def _to_native(field: str, item: Any) -> NativeColumnRule:
    if isinstance(item, dict):
        kind = str(item.get("kind") or item.get("type") or "pyspark_column")
        expr_ref = item.get("expr_ref") or item.get("ref") or item.get("callable")
        meta = {
            k: v
            for k, v in item.items()
            if k
            not in {
                "kind",
                "type",
                "field",
                "expr_ref",
                "ref",
                "callable",
                "required",
                "node",
            }
        }
        return NativeColumnRule(
            field=str(item.get("field") or field),
            kind=kind,
            expr_ref=str(expr_ref) if expr_ref is not None else None,
            required=bool(item.get("required", True)),
            metadata=meta,
        )
    if callable(item) and not isinstance(item, (str, bytes, type)):
        return NativeColumnRule(
            field=field,
            kind="pyspark_callable",
            expr_ref=getattr(item, "__qualname__", getattr(item, "__name__", None)),
            metadata={"callable_type": type(item).__name__},
        )
    return NativeColumnRule(
        field=field,
        kind="pyspark_column",
        metadata={
            "column_type": type(item).__name__,
            "column_module": type(item).__module__,
        },
    )
