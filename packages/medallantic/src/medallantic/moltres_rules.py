"""Non-portable Moltres / SQL-native quality rules (Medallantic-only).

These rules are **not** part of ``etlantic.quality/1``. They require the
``quality.moltres_expr`` engine capability and fail closed with ``MDL132``
when the selected engine cannot execute them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

MOLTRES_RULE_KINDS = frozenset(
    {
        "moltres_expr",
        "moltres",
        "moltres_column",
        "moltres_callable",
        "sqlalchemy_expr",
        "sa_expr",
    }
)

MOLTRES_QUALITY_CAPABILITY = "quality.moltres_expr"


@dataclass(frozen=True, slots=True)
class NativeMoltresRule:
    """One engine-native Moltres / SQLAlchemy expression validator."""

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


def is_moltres_rule_entry(item: Any) -> bool:
    """Return True when a rule entry is a Moltres / SQLAlchemy-native validator."""
    if isinstance(item, dict):
        kind = str(item.get("kind") or item.get("type") or "").strip().lower()
        return kind in MOLTRES_RULE_KINDS
    type_name = type(item).__name__
    module = type(item).__module__ or ""
    if "moltres" in module.lower():
        return True
    return "sqlalchemy" in module and type_name in {
        "ColumnElement",
        "BinaryExpression",
        "UnaryExpression",
        "Label",
        "ClauseElement",
    }


def split_portable_and_moltres_rules(
    rules: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[NativeMoltresRule]]:
    """Partition a rules mapping into portable shorthand and Moltres rules."""
    if not rules:
        return {}, []
    portable: dict[str, Any] = {}
    native: list[NativeMoltresRule] = []
    for field_key, entries in rules.items():
        field_name = str(field_key)
        items = list(entries) if isinstance(entries, (list, tuple)) else [entries]
        portable_items: list[Any] = []
        for item in items:
            if is_moltres_rule_entry(item):
                native.append(_to_native(field_name, item))
            else:
                portable_items.append(item)
        if portable_items:
            portable[field_name] = portable_items
    return portable, native


def _to_native(field: str, item: Any) -> NativeMoltresRule:
    if isinstance(item, dict):
        kind = str(item.get("kind") or item.get("type") or "moltres_expr")
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
        return NativeMoltresRule(
            field=str(item.get("field") or field),
            kind=kind,
            expr_ref=str(expr_ref) if expr_ref is not None else None,
            required=bool(item.get("required", True)),
            metadata=meta,
        )
    if callable(item) and not isinstance(item, (str, bytes, type)):
        return NativeMoltresRule(
            field=field,
            kind="moltres_callable",
            expr_ref=getattr(item, "__qualname__", getattr(item, "__name__", None)),
            metadata={"callable_type": type(item).__name__},
        )
    return NativeMoltresRule(
        field=field,
        kind="moltres_expr",
        metadata={
            "expr_type": type(item).__name__,
            "expr_module": type(item).__module__,
        },
    )
