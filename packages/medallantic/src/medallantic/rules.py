"""Medallantic shorthand rule DSL → ``etlantic.quality/1``."""

from __future__ import annotations

from typing import Any

from etlantic.quality.model import (
    QualityRule,
    QualityRuleset,
    rule_compare,
    rule_custom_contract,
    rule_length,
    rule_membership,
    rule_not_null,
    rule_range,
    rule_regex,
    rule_uniqueness,
)


class RuleDSLError(ValueError):
    """Raised when a Medallantic rules shorthand cannot be parsed."""


def parse_rules_shorthand(
    rules: dict[str, Any] | None,
    *,
    name: str | None = None,
) -> QualityRuleset:
    """Parse column→shorthand lists into a portable quality ruleset.

    Supported shorthands (strings)::

        not_null
        unique / uniqueness
        regex:<pattern>
        length:min:max | min_length:N | max_length:N
        in:a|b|c
        range:min:max
        ge:N / le:N / gt:N / lt:N / eq:N / ne:N
        custom:<name>

    Structured dict forms are also accepted per entry.
    """
    if not rules:
        return QualityRuleset(name=name, rules=())
    parsed: list[QualityRule] = []
    for field, entries in rules.items():
        field_name = str(field)
        items = entries if isinstance(entries, (list, tuple)) else [entries]
        for item in items:
            parsed.append(_parse_one(field_name, item))
    return QualityRuleset(name=name, rules=tuple(parsed))


def _parse_one(field: str, item: Any) -> QualityRule:
    if isinstance(item, str):
        return _parse_string(field, item)
    if isinstance(item, dict):
        kind = str(item.get("kind") or item.get("type") or "")
        if not kind:
            raise RuleDSLError(f"Rule for {field!r} is missing kind")
        node = dict(item.get("node") or {})
        for key, value in item.items():
            if key in {"kind", "type", "field", "node", "required", "rule_id"}:
                continue
            node.setdefault(key, value)
        return QualityRule(
            kind=kind if kind != "unique" else "uniqueness",
            field=str(item.get("field") or field),
            node=node,
            required=bool(item.get("required", True)),
            rule_id=(str(item["rule_id"]) if item.get("rule_id") is not None else None),
        )
    raise RuleDSLError(f"Unsupported rule entry for {field!r}: {type(item)!r}")


def _parse_string(field: str, raw: str) -> QualityRule:
    text = raw.strip()
    lower = text.lower()
    if lower in {"not_null", "notnull", "non_null"}:
        return rule_not_null(field)
    if lower in {"unique", "uniqueness"}:
        return rule_uniqueness(field)
    if lower.startswith("regex:"):
        return rule_regex(field, text.split(":", 1)[1])
    if lower.startswith("in:"):
        values = text.split(":", 1)[1].split("|")
        return rule_membership(field, [v for v in values if v != ""])
    if lower.startswith("range:"):
        parts = text.split(":")
        if len(parts) != 3:
            raise RuleDSLError(f"Invalid range shorthand {raw!r}")
        return rule_range(
            field,
            min_value=_num(parts[1], raw=raw),
            max_value=_num(parts[2], raw=raw),
        )
    if lower.startswith("length:"):
        parts = text.split(":")
        if len(parts) == 3:
            return rule_length(
                field,
                min_length=_int_bound(parts[1], raw=raw),
                max_length=_int_bound(parts[2], raw=raw),
            )
        raise RuleDSLError(f"Invalid length shorthand {raw!r}")
    if lower.startswith("min_length:"):
        return rule_length(field, min_length=_int_bound(text.split(":", 1)[1], raw=raw))
    if lower.startswith("max_length:"):
        return rule_length(field, max_length=_int_bound(text.split(":", 1)[1], raw=raw))
    for op in ("ge", "le", "gt", "lt", "eq", "ne"):
        if lower.startswith(f"{op}:"):
            return rule_compare(field, op, _num(text.split(":", 1)[1], raw=raw))
    if lower.startswith("custom:"):
        return rule_custom_contract(text.split(":", 1)[1], field=field)
    raise RuleDSLError(f"Unknown rule shorthand {raw!r} for field {field!r}")


def _int_bound(value: str, *, raw: str) -> int:
    text = value.strip()
    if not text:
        raise RuleDSLError(f"Invalid length/numeric bound in {raw!r}")
    try:
        return int(text)
    except ValueError as exc:
        raise RuleDSLError(f"Invalid integer bound in {raw!r}") from exc


def _num(value: str, *, raw: str | None = None) -> Any:
    text = value.strip()
    if not text:
        label = raw or value
        raise RuleDSLError(f"Empty numeric bound in {label!r}")
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return text
