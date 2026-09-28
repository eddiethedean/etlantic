# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Evaluate portable quality rules against row mappings (engine-neutral)."""

from __future__ import annotations

import operator
import re
from typing import Any, cast

from etlantic.quality.model import QualityRule, QualityRuleset

_COMPARE_OPERATORS = {
    "eq": operator.eq,
    "ne": operator.ne,
    "lt": operator.lt,
    "le": operator.le,
    "gt": operator.gt,
    "ge": operator.ge,
}


def _as_mapping(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return row
    if hasattr(row, "model_dump"):
        return dict(row.model_dump())
    if hasattr(row, "__dict__"):
        return {k: v for k, v in vars(row).items() if not k.startswith("_")}
    raise TypeError(f"Cannot coerce row of type {type(row)!r} to mapping")


def _is_missing(value: Any) -> bool:
    """True for None and IEEE / pandas missing float values."""
    if value is None:
        return True
    try:
        import math

        if isinstance(value, float) and math.isnan(value):
            return True
    except Exception:
        pass
    # Avoid importing pandas on the hot path; recognize common NA sentinels.
    return type(value).__name__ in {"NAType", "NaTType"}


def evaluate_rule(rule: QualityRule, row: dict[str, Any]) -> str | None:
    """Return a failure reason string, or ``None`` when the rule passes."""
    kind = rule.kind
    field = rule.field
    node = rule.node
    value = row.get(field) if field else None

    if kind == "not_null":
        if _is_missing(value):
            return f"{field} is null"
        return None

    if kind == "compare":
        op = str(node.get("op") or "")
        expected: Any = node.get("value")
        if _is_missing(value):
            return f"{field} is null"
        if value is None:
            return f"{field} is null"
        compare = _COMPARE_OPERATORS.get(op)
        if compare is None:
            return f"{field} unsupported compare op {op!r}"
        try:
            ok = compare(value, expected)
        except TypeError:
            return f"{field} compare {op!r} type error"
        return None if ok else f"{field} failed {op} {expected!r}"

    if kind == "membership":
        values = list(node.get("values") or [])
        allowed = bool(node.get("allowed", True))
        if _is_missing(value):
            return f"{field} is null"
        if allowed:
            return None if value in values else f"{field} not in allowed values"
        return None if value not in values else f"{field} in disallowed values"

    if kind == "range":
        min_value = node.get("min_value")
        max_value = node.get("max_value")
        if _is_missing(value):
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
        if _is_missing(value):
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
        if _is_missing(value):
            return f"{field} is null"
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

        # Normalize each shared field set once before applying rule severity.
        canonical_keys, duplicate_fields, uniqueness_errors = _prepare_uniqueness_keys(
            row, uniqueness_specs, seen_keys
        )
        # Optional uniqueness failures remain soft warnings.
        for fields, required in uniqueness_specs:
            if fields in uniqueness_errors:
                message = _uniqueness_failure_message(fields, uniqueness_errors[fields])
            elif fields in duplicate_fields:
                message = f"duplicate key on {','.join(fields)}"
            else:
                continue
            (reasons if required else soft_reasons).append(message)

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
            # Only accepted rows consume uniqueness keys.
            for fields, _required in uniqueness_specs:
                key = canonical_keys.get(fields)
                if key is None:
                    continue
                seen_keys[fields].add(key)
            valid.append(item)

    return valid, invalid, diagnostics


class _UnsupportedUniquenessValue(ValueError):
    """A uniqueness value cannot be converted to a stable set key."""


def _canonical_uniqueness_value(
    value: Any,
    *,
    path: str,
    active_containers: set[int] | None = None,
) -> tuple[Any, ...]:
    """Return a type-aware, hashable key for a supported field value."""
    if active_containers is None:
        active_containers = set()

    value_type: type[Any] = cast(type[Any], type(value))
    if value is None:
        return ("none",)
    if value_type is bool:
        return ("bool", value)
    if value_type is int:
        return ("int", value)
    if value_type is float:
        # Keep Python float equality; float.hex distinguishes signed zero.
        return ("float", 0.0 if value == 0.0 else value)
    if value_type is str:
        return ("str", value)
    if value_type is bytes:
        return ("bytes", value)

    if isinstance(value, (list, tuple, dict)):
        container: object = cast(object, value)
        identity: int = id(container)
        if identity in active_containers:
            raise _UnsupportedUniquenessValue(
                f"{path} contains a cyclic {value_type.__name__}"
            )
        active_containers.add(identity)
        try:
            if isinstance(value, list):
                list_items: list[Any] = cast(list[Any], value)
                return (
                    "list",
                    tuple(
                        _canonical_uniqueness_value(
                            item,
                            path=f"{path}[{index}]",
                            active_containers=active_containers,
                        )
                        for index, item in enumerate(list_items)
                    ),
                )
            if isinstance(value, tuple):
                tuple_items: tuple[Any, ...] = cast(tuple[Any, ...], value)
                return (
                    "tuple",
                    tuple(
                        _canonical_uniqueness_value(
                            item,
                            path=f"{path}[{index}]",
                            active_containers=active_containers,
                        )
                        for index, item in enumerate(tuple_items)
                    ),
                )

            dict_items: dict[Any, Any] = cast(dict[Any, Any], value)
            entries = [
                (
                    _canonical_uniqueness_value(
                        key,
                        path=f"{path} key",
                        active_containers=active_containers,
                    ),
                    _canonical_uniqueness_value(
                        item,
                        path=f"{path} value",
                        active_containers=active_containers,
                    ),
                )
                for key, item in dict_items.items()
            ]
            # Dict insertion order does not affect structural uniqueness.
            return ("dict", frozenset(entries))
        except _UnsupportedUniquenessValue:
            raise
        except Exception as exc:
            raise _UnsupportedUniquenessValue(
                f"{path} could not be normalized ({value_type.__name__})"
            ) from exc
        finally:
            active_containers.remove(identity)

    # Preserve support for hashable scalar types such as dates, decimals, and
    # UUIDs, while keeping them distinct from other Python types with equal values.
    try:
        hash(value)
    except Exception as exc:
        raise _UnsupportedUniquenessValue(
            f"{path} has unsupported unhashable type {value_type.__name__}"
        ) from exc
    return ("scalar", value_type, value)


def _prepare_uniqueness_keys(
    row: dict[str, Any],
    uniqueness_specs: list[tuple[tuple[str, ...], bool]],
    seen_keys: dict[tuple[str, ...], set[tuple[Any, ...]]],
) -> tuple[
    dict[tuple[str, ...], tuple[Any, ...]],
    set[tuple[str, ...]],
    dict[tuple[str, ...], str],
]:
    """Normalize row keys and compare them with keys from accepted rows."""
    canonical_keys: dict[tuple[str, ...], tuple[Any, ...]] = {}
    duplicate_fields: set[tuple[str, ...]] = set()
    errors: dict[tuple[str, ...], str] = {}
    for fields, _required in uniqueness_specs:
        if fields in canonical_keys or fields in errors:
            continue
        values = tuple(row.get(field) for field in fields)
        if any(_is_missing(value) for value in values):
            continue
        try:
            key = tuple(
                _canonical_uniqueness_value(value, path=f"field {field!r}")
                for field, value in zip(fields, values, strict=True)
            )
            hash(key)
        except _UnsupportedUniquenessValue as exc:
            errors[fields] = str(exc)
            continue
        except TypeError:
            errors[fields] = "key values cannot be hashed safely"
            continue

        canonical_keys[fields] = key
        try:
            if key in seen_keys[fields]:
                duplicate_fields.add(fields)
        except TypeError:
            canonical_keys.pop(fields)
            errors[fields] = "key values cannot be compared safely"
    return canonical_keys, duplicate_fields, errors


def _uniqueness_failure_message(fields: tuple[str, ...], error: str) -> str:
    """Format a clear row diagnostic for an unsupported uniqueness key."""
    return f"uniqueness key on {','.join(fields)} cannot be evaluated: {error}"
