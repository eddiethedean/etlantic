"""Evaluate portable quality rules against row mappings (engine-neutral)."""

from __future__ import annotations

import re
from typing import Any

from etlantic.quality.model import QualityRule, QualityRuleset


def _as_mapping(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return row
    if hasattr(row, "model_dump"):
        return dict(row.model_dump())
    if hasattr(row, "__dict__"):
        return {k: v for k, v in vars(row).items() if not k.startswith("_")}
    raise TypeError(f"Cannot coerce row of type {type(row)!r} to mapping")


def evaluate_rule(rule: QualityRule, row: dict[str, Any]) -> str | None:
    """Return a failure reason string, or ``None`` when the rule passes."""
    kind = rule.kind
    field = rule.field
    node = rule.node
    value = row.get(field) if field else None

    if kind == "not_null":
        if value is None:
            return f"{field} is null"
        return None

    if kind == "compare":
        op = str(node.get("op") or "")
        expected = node.get("value")
        if value is None:
            return f"{field} is null"
        try:
            ok = {
                "eq": value == expected,
                "ne": value != expected,
                "lt": value < expected,
                "le": value <= expected,
                "gt": value > expected,
                "ge": value >= expected,
            }.get(op)
        except TypeError:
            return f"{field} compare {op!r} type error"
        if ok is None:
            return f"{field} unsupported compare op {op!r}"
        return None if ok else f"{field} failed {op} {expected!r}"

    if kind == "membership":
        values = list(node.get("values") or [])
        allowed = bool(node.get("allowed", True))
        if allowed:
            return None if value in values else f"{field} not in allowed values"
        return None if value not in values else f"{field} in disallowed values"

    if kind == "range":
        min_value = node.get("min_value")
        max_value = node.get("max_value")
        if value is None:
            return f"{field} is null"
        try:
            if min_value is not None and value < min_value:
                return f"{field} below min_value"
            if max_value is not None and value > max_value:
                return f"{field} above max_value"
        except TypeError:
            return f"{field} range type error"
        return None

    if kind == "regex":
        pattern = str(node.get("pattern") or "")
        if value is None:
            return f"{field} is null"
        if not isinstance(value, str):
            return f"{field} is not a string"
        try:
            if re.search(pattern, value) is None:
                return f"{field} does not match pattern"
        except re.error as exc:
            return f"{field} invalid regex pattern: {exc}"
        return None

    if kind == "length":
        if value is None:
            return f"{field} is null"
        length = len(value) if hasattr(value, "__len__") else None
        if length is None:
            return f"{field} has no length"
        min_length = node.get("min_length")
        max_length = node.get("max_length")
        try:
            if min_length is not None and length < int(min_length):
                return f"{field} shorter than min_length"
            if max_length is not None and length > int(max_length):
                return f"{field} longer than max_length"
        except (TypeError, ValueError):
            return f"{field} length bound type error"
        return None

    if kind == "uniqueness":
        # Uniqueness is evaluated at batch level in split_by_quality.
        return None

    if kind == "custom_contract":
        # Portable core cannot evaluate custom contracts; always fail closed.
        # Engines that advertise quality.custom_contract must supply their own
        # evaluator rather than relying on this path.
        name = str(node.get("name") or "custom")
        return f"custom_contract {name!r} not evaluated by portable core"

    return f"unknown rule kind {kind!r}"


def split_by_quality(
    records: list[Any],
    ruleset: QualityRuleset,
) -> tuple[list[Any], list[Any], list[dict[str, Any]]]:
    """Split records into accepted/rejected using portable quality rules.

    Uniqueness rules are applied after per-row checks using the first
    occurrence as accepted. Optional (``required=False``) rule failures are
    recorded as soft diagnostics and do not reject the row.
    """
    uniqueness_specs: list[tuple[tuple[str, ...], bool]] = []
    row_rules = []
    for rule in ruleset.rules:
        if rule.kind == "uniqueness":
            fields = tuple(
                rule.node.get("fields") or ([rule.field] if rule.field else [])
            )
            if fields:
                uniqueness_specs.append((fields, bool(rule.required)))
        else:
            row_rules.append(rule)

    valid: list[Any] = []
    invalid: list[Any] = []
    diagnostics: list[dict[str, Any]] = []
    seen_keys: dict[tuple[str, ...], set[tuple[Any, ...]]] = {
        fields: set() for fields, _required in uniqueness_specs
    }

    for index, item in enumerate(records):
        try:
            row = _as_mapping(item)
        except TypeError as exc:
            invalid.append(item)
            diagnostics.append(
                {
                    "code": "PMQTY400",
                    "message": str(exc),
                    "row_index": index,
                    "severity": "error",
                }
            )
            continue

        reasons: list[str] = []
        soft_reasons: list[str] = []
        for rule in row_rules:
            reason = evaluate_rule(rule, row)
            if reason is None:
                continue
            if rule.required:
                reasons.append(reason)
            else:
                soft_reasons.append(reason)

        for fields, required in uniqueness_specs:
            key = tuple(row.get(f) for f in fields)
            bucket = seen_keys[fields]
            if key in bucket:
                message = f"duplicate key on {','.join(fields)}"
                if required:
                    reasons.append(message)
                else:
                    soft_reasons.append(message)
            else:
                bucket.add(key)

        if soft_reasons:
            diagnostics.append(
                {
                    "code": "PMQTY410",
                    "message": "; ".join(soft_reasons),
                    "row_index": index,
                    "severity": "warning",
                    "reasons": soft_reasons,
                    "optional": True,
                }
            )

        if reasons:
            invalid.append(item)
            diagnostics.append(
                {
                    "code": "PMQTY410",
                    "message": "; ".join(reasons),
                    "row_index": index,
                    "severity": "error",
                    "reasons": reasons,
                }
            )
        else:
            valid.append(item)

    return valid, invalid, diagnostics
