"""Schema history row-payload and subject-path collision regressions."""

from __future__ import annotations

import pytest

from etlantic.schema_drift import NormalizedField, NormalizedSchema, SchemaObservation
from etlantic.schema_history import (
    FileSchemaHistoryProvider,
    assert_no_row_payload,
    subject_history_filename,
)


def _schema(*fields: str) -> NormalizedSchema:
    return NormalizedSchema(
        identity="t",
        fields=tuple(NormalizedField(name=f, logical_type="string") for f in fields),
    )


def test_field_metadata_rows_fail_closed() -> None:
    schema = NormalizedSchema(
        identity="t",
        fields=(
            NormalizedField(
                name="id",
                logical_type="int",
                metadata={"examples": [{"id": 1}]},
            ),
        ),
    )
    obs = SchemaObservation(subject_id="s", schema=schema)
    with pytest.raises(ValueError, match="must not store source rows"):
        assert_no_row_payload(obs)


def test_subject_paths_do_not_collide() -> None:
    assert subject_history_filename("foo:bar") != subject_history_filename("foo_bar")
    assert subject_history_filename("safe-id") == "safe-id.json"


def test_file_history_keeps_distinct_subjects(tmp_path) -> None:
    provider = FileSchemaHistoryProvider(tmp_path)
    a = SchemaObservation(subject_id="foo:bar", schema=_schema("a"))
    b = SchemaObservation(subject_id="foo_bar", schema=_schema("b"))
    provider.record(a)
    provider.record(b)
    assert provider.latest("foo:bar") is not None
    assert provider.latest("foo_bar") is not None
    assert provider.latest("foo:bar").schema.fields[0].name == "a"
    assert provider.latest("foo_bar").schema.fields[0].name == "b"
