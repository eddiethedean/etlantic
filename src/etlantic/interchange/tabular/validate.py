# pyright: reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnnecessaryIsInstance=false
"""Fail-closed validation for versioned interchange descriptors."""

from __future__ import annotations

from typing import Any

from etlantic.interchange.tabular.descriptor import (
    CopyEligibility,
    InterchangeDescriptor,
)
from etlantic.interchange.tabular.errors import InterchangeDescriptorError
from etlantic.interchange.tabular.mechanisms import (
    SCHEMA,
    InterchangeMechanism,
)

_FIELDS = {
    "schema",
    "mechanism",
    "producer_engine",
    "consumer_engine",
    "producer_caps",
    "consumer_caps",
    "schema_fingerprint",
    "ownership",
    "batching",
    "collection",
    "copy_eligibility",
    "fallback_reason",
    "evidence_refs",
}


def _string(data: dict[str, Any], field: str) -> str:
    value = data[field]
    if not isinstance(value, str) or not value:
        raise InterchangeDescriptorError(
            f"Interchange descriptor field {field!r} must be a non-empty string."
        )
    return value


def _strings(data: dict[str, Any], field: str) -> tuple[str, ...]:
    value = data[field]
    if not isinstance(value, (list, tuple)) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise InterchangeDescriptorError(
            f"Interchange descriptor field {field!r} must be a string sequence."
        )
    return tuple(value)


def validate_descriptor(data: dict[str, Any]) -> InterchangeDescriptor:
    """Validate an exact ``etlantic.interchange/1`` descriptor."""
    if not isinstance(data, dict):
        raise InterchangeDescriptorError("Interchange descriptor must be a dictionary.")

    fields = set(data)
    missing = _FIELDS - fields
    unknown = fields - _FIELDS
    if missing:
        raise InterchangeDescriptorError(
            f"Interchange descriptor is missing fields: {sorted(missing)!r}."
        )
    if unknown:
        raise InterchangeDescriptorError(
            f"Interchange descriptor has unknown fields: {sorted(unknown)!r}."
        )

    schema = _string(data, "schema")
    if schema != SCHEMA:
        raise InterchangeDescriptorError(
            f"Unsupported interchange descriptor schema {schema!r}; "
            f"expected {SCHEMA!r}."
        )

    try:
        mechanism = InterchangeMechanism(_string(data, "mechanism"))
    except ValueError as exc:
        raise InterchangeDescriptorError(
            f"Unknown interchange mechanism {data['mechanism']!r}."
        ) from exc

    try:
        copy_eligibility = CopyEligibility(_string(data, "copy_eligibility"))
    except ValueError as exc:
        raise InterchangeDescriptorError(
            f"Unknown copy eligibility {data['copy_eligibility']!r}."
        ) from exc

    collection = data["collection"]
    if not isinstance(collection, bool):
        raise InterchangeDescriptorError(
            "Interchange descriptor field 'collection' must be a boolean."
        )

    fallback_reason = data["fallback_reason"]
    if fallback_reason is not None and (
        not isinstance(fallback_reason, str) or not fallback_reason
    ):
        raise InterchangeDescriptorError(
            "Interchange descriptor field 'fallback_reason' must be null "
            "or a non-empty string."
        )

    fallback_mechanisms = {
        InterchangeMechanism.RECORDS_FALLBACK,
        InterchangeMechanism.NATIVE_FALLBACK,
    }
    if mechanism in fallback_mechanisms and fallback_reason is None:
        raise InterchangeDescriptorError(
            "Fallback mechanisms require an explicit fallback_reason."
        )
    if mechanism not in fallback_mechanisms and fallback_reason is not None:
        raise InterchangeDescriptorError(
            "Non-fallback mechanisms cannot declare a fallback_reason."
        )

    return InterchangeDescriptor(
        schema=schema,
        mechanism=mechanism,
        producer_engine=_string(data, "producer_engine"),
        consumer_engine=_string(data, "consumer_engine"),
        producer_caps=_strings(data, "producer_caps"),
        consumer_caps=_strings(data, "consumer_caps"),
        schema_fingerprint=_string(data, "schema_fingerprint"),
        ownership=_string(data, "ownership"),
        batching=_string(data, "batching"),
        collection=collection,
        copy_eligibility=copy_eligibility,
        fallback_reason=fallback_reason,
        evidence_refs=_strings(data, "evidence_refs"),
    )
