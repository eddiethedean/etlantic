"""JSON-safe effective parameter authority for requested adaptive plans."""

from __future__ import annotations

import json
import math
from types import MappingProxyType
from typing import Any


def canonical_parameters(value: Any) -> str:
    remaining = 10000
    text_remaining = 1024 * 1024
    active = set()

    def safe(item: Any, depth: int = 0) -> Any:
        nonlocal remaining, text_remaining
        remaining -= 1
        if remaining < 0 or depth > 32:
            raise ValueError("Adaptive parameter bounds exceeded")
        if item is None or type(item) in {str, bool, int}:
            if (type(item) is str and len(item) > 65536) or (
                type(item) is int and item.bit_length() > 4096
            ):
                raise ValueError("Adaptive parameter bounds exceeded")
            if type(item) is str:
                text_remaining -= len(item) * 6
            elif type(item) is int:
                text_remaining -= 1234
            if text_remaining < 0:
                raise ValueError("Adaptive parameter bounds exceeded")
            return item
        if type(item) is float and math.isfinite(item):
            return item
        if isinstance(item, (dict, MappingProxyType, list, tuple)):
            if id(item) in active or len(item) > remaining:
                raise ValueError("Adaptive parameter bounds exceeded")
            active.add(id(item))
            try:
                if isinstance(item, (dict, MappingProxyType)):
                    if any(type(key) is not str or len(key) > 4096 for key in item):
                        raise ValueError("Invalid adaptive parameter keys")
                    text_remaining -= sum(len(key) * 6 for key in item)
                    if text_remaining < 0:
                        raise ValueError("Adaptive parameter bounds exceeded")
                    return {key: safe(val, depth + 1) for key, val in item.items()}
                return [safe(val, depth + 1) for val in item]
            finally:
                active.remove(id(item))
        raise ValueError("Adaptive parameters must be JSON-safe")

    encoded = json.dumps(
        safe(value), sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    if len(encoded) > 1024 * 1024:
        raise ValueError("Adaptive parameter bounds exceeded")
    return encoded


def capture_parameters(graph: Any, request: Any) -> dict[str, Any]:
    canonical_parameters(request.parameter_overrides)
    captured = {}
    for node in graph.nodes:
        if not node.parameters:
            continue
        values = {}
        overrides = request.parameter_overrides.get(node.name, {})
        if type(overrides) not in {dict, MappingProxyType} or set(overrides) - {
            p.name for p in node.parameters
        }:
            raise ValueError("Unknown adaptive parameter override")
        for parameter in node.parameters:
            value = overrides.get(
                parameter.name,
                parameter.value
                if parameter.has_value
                else parameter.default
                if parameter.has_default
                else ...,
            )
            if value is ...:
                raise ValueError("Missing effective adaptive parameter")
            values[parameter.name] = value
        captured[node.name] = values
    return json.loads(canonical_parameters(captured))


def validate_parameters(graph: Any, request: Any, captured: Any) -> dict[str, Any]:
    canonical_parameters(request.parameter_overrides)
    expected = {
        n.name: {p.name for p in n.parameters} for n in graph.nodes if n.parameters
    }
    if captured is None:
        if expected:
            raise ValueError(
                "Legacy parameterized adaptive plan lacks effective capture"
            )
        return {}
    if type(captured) not in {dict, MappingProxyType} or set(captured) != set(expected):
        raise ValueError("Adaptive parameter capture node coverage drifted")
    canonical_parameters(captured)
    for node in graph.nodes:
        overrides = request.parameter_overrides.get(node.name, {})
        if type(overrides) not in {dict, MappingProxyType} or set(overrides) - {
            p.name for p in node.parameters
        }:
            raise ValueError("Unknown adaptive parameter override")
        if not node.parameters:
            continue
        values = captured[node.name]
        if (
            type(values) not in {dict, MappingProxyType}
            or set(values) != expected[node.name]
        ):
            raise ValueError("Adaptive parameter capture name coverage drifted")
        for parameter in node.parameters:
            # Historical wire records intentionally omit live values. Capture
            # supplies authority after JSON; available live values must agree.
            live = overrides.get(
                parameter.name,
                parameter.value
                if parameter.has_value and parameter.value is not ...
                else parameter.default
                if parameter.has_default
                else ...,
            )
            if live is not ... and canonical_parameters(live) != canonical_parameters(
                values[parameter.name]
            ):
                raise ValueError("Adaptive effective parameter value drifted")
            if (
                parameter.has_value
                and parameter.value is not ...
                and canonical_parameters(parameter.value)
                != canonical_parameters(values[parameter.name])
            ):
                raise ValueError("Adaptive live parameter value drifted")
    return captured
