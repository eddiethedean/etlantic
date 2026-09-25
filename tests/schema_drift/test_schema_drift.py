"""Schema drift model tests."""

from __future__ import annotations

import csv

import pytest

from etlantic import Data
from etlantic.schema_drift import (
    DriftImpact,
    NormalizedField,
    NormalizedSchema,
    diff_normalized_schemas,
    json_safe_metadata,
    normalize_schema_from_fields,
    normalize_schema_from_model,
)


class Left(Data):
    id: int
    name: str


class Right(Data):
    id: int
    name: str | None = None
    email: str = ""


class Reverse(Data):
    z: int
    a: str


def test_equivalent_models_same_fingerprint() -> None:
    a = normalize_schema_from_model(Left)
    b = normalize_schema_from_model(Left)
    assert a.fingerprint() == b.fingerprint()


def test_model_normalization_preserves_declaration_order() -> None:
    schema = normalize_schema_from_model(Reverse)

    assert [field.name for field in schema.fields] == ["z", "a"]


def test_operational_diff_detects_add_and_nullability() -> None:
    # Use field lists so nullability is explicit (Union types may normalize as
    # distinct logical types rather than nullable string).
    left = normalize_schema_from_fields(
        [
            {
                "name": "id",
                "logical_type": "integer",
                "nullable": False,
                "required": True,
            },
            {
                "name": "name",
                "logical_type": "string",
                "nullable": False,
                "required": True,
            },
        ],
        identity="s",
    )
    right = normalize_schema_from_fields(
        [
            {
                "name": "id",
                "logical_type": "integer",
                "nullable": False,
                "required": True,
            },
            {
                "name": "name",
                "logical_type": "string",
                "nullable": True,
                "required": False,
            },
            {
                "name": "email",
                "logical_type": "string",
                "nullable": False,
                "required": False,
            },
        ],
        identity="s",
    )
    change_set = diff_normalized_schemas(left, right)
    by_kind = {c.kind: c for c in change_set.changes}
    assert by_kind["field_added"].path == "email"
    assert by_kind["nullability_changed"].path == "name"
    assert by_kind["nullability_changed"].impact is DriftImpact.CONDITIONALLY_COMPATIBLE
    assert change_set.overall_impact is DriftImpact.CONDITIONALLY_COMPATIBLE


def test_model_union_optional_is_detected() -> None:
    """ContractModel Optional/Union may surface as type_changed; still must fail closed."""
    change_set = diff_normalized_schemas(
        normalize_schema_from_model(Left),
        normalize_schema_from_model(Right),
    )
    kinds = {c.kind for c in change_set.changes}
    assert "field_added" in kinds
    assert kinds & {"nullability_changed", "type_changed"}
    assert change_set.overall_impact is DriftImpact.BREAKING


def test_field_list_normalization_ignores_physical_metadata_in_fingerprint() -> None:
    a = normalize_schema_from_fields(
        [{"name": "id", "logical_type": "int", "physical": "int64"}],
        identity="s",
    )
    b = normalize_schema_from_fields(
        [{"name": "id", "logical_type": "int", "physical": "INT"}],
        identity="s",
    )
    assert a.fingerprint() == b.fingerprint()


def test_wire_identity_is_private_collision_resistant_and_fingerprintable() -> None:
    field = NormalizedField("id", "integer")
    left = NormalizedSchema("/Users/alice/data/events.csv", (field,))
    right = NormalizedSchema("/Users/bob/data/events.csv", (field,))

    left_wire = left.to_dict()
    right_wire = right.to_dict()

    assert "/Users/" not in left_wire["identity"]
    assert left_wire["identity"].startswith("path-sha256:")
    assert left_wire["identity"] != right_wire["identity"]
    assert (
        left_wire["fingerprint"] == NormalizedSchema.from_dict(left_wire).fingerprint()
    )
    assert left.fingerprint() != right.fingerprint()


def test_lineage_and_parser_control_metadata_round_trip_as_typed_values() -> None:
    schema = NormalizedSchema(
        "events",
        (NormalizedField("id", "integer"),),
        metadata={
            "lineage_graph": {
                "version": 1,
                "fields": {
                    "id": {
                        "source_nodes": ["events"],
                        "source_fields": ["id"],
                        "qualified_source_fields": ["events.id"],
                        "operations": [],
                        "invertible": True,
                    }
                },
            },
            "lineage": {
                "id": {
                    "field": "id",
                    "source_node": "events",
                    "source_fields": ["id"],
                    "qualified_source_fields": ["events.id"],
                    "source_types": {"id": "integer"},
                    "operations": [],
                    "invertible": True,
                }
            },
            "parser_options": {
                "encoding": "utf-8",
                "delimiter": "|",
                "quotechar": '"',
                "strict": True,
                "skipinitialspace": False,
            },
            "capabilities": {"write_modes": ["append"], "create": True},
        },
    )

    restored = NormalizedSchema.from_dict(schema.to_dict())
    assert restored.metadata["lineage_graph"]["fields"]["id"]["invertible"] is True
    assert restored.metadata["lineage"]["id"]["invertible"] is True
    assert restored.metadata["parser_options"]["delimiter"] == "|"
    assert restored.metadata["parser_options"]["strict"] is True
    assert restored.metadata["capabilities"] == {
        "write_modes": ["append"],
        "create": True,
    }


def test_csv_quoting_modes_available_on_this_python_round_trip() -> None:
    for name in (
        "QUOTE_MINIMAL",
        "QUOTE_ALL",
        "QUOTE_NONNUMERIC",
        "QUOTE_NONE",
        "QUOTE_NOTNULL",
        "QUOTE_STRINGS",
    ):
        if hasattr(csv, name):
            mode = getattr(csv, name)
            assert json_safe_metadata({"parser_options": {"quoting": mode}}) == {
                "parser_options": {"quoting": mode}
            }


def test_control_field_names_do_not_expand_global_metadata_allowlist() -> None:
    safe = json_safe_metadata(
        {
            "provider_metadata": {
                "encoding": "PRIVATE_TOKEN",
                "strict": "PRIVATE_TOKEN",
                "invertible": "not-a-boolean",
            }
        }
    )
    assert safe == {
        "provider_metadata": {
            "encoding": "<redacted>",
            "strict": "<redacted>",
            "invertible": "<redacted>",
        }
    }
    with pytest.raises(ValueError, match="lineage metadata"):
        json_safe_metadata({"provider_metadata": {"lineage_graph": "PRIVATE_TOKEN"}})


def test_provider_capability_sequences_are_allowlisted() -> None:
    assert json_safe_metadata({"capabilities": ["append", "create"]}) == {
        "capabilities": ["append", "create"]
    }
    with pytest.raises(ValueError, match="unsupported operation"):
        json_safe_metadata({"capabilities": ["PRIVATE_TOKEN"]})


@pytest.mark.parametrize(
    "metadata",
    [
        {"parser_options": {"unknown_option": True}},
        {"parser_options": {"strict": "yes"}},
        {"parser_options": {"delimiter": "/Users/alice/secret"}},
        {"capabilities": {"provider_payload": "untrusted"}},
        {"capabilities": ["PRIVATE_TOKEN"]},
        {"lineage_graph": {"version": 1, "fields": {"id": {"secret": "x"}}}},
    ],
)
def test_unsupported_control_metadata_is_rejected(metadata: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        json_safe_metadata(metadata)
