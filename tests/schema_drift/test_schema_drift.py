"""Schema drift model tests."""

from __future__ import annotations

from etlantic import Data
from etlantic.schema_drift import (
    DriftImpact,
    diff_normalized_schemas,
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
