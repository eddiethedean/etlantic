# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportMissingParameterType=false, reportMissingTypeArgument=false, reportOptionalMemberAccess=false, reportOptionalSubscript=false, reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownVariableType=false
"""Regression coverage for the 0.55 review closure work."""

import asyncio
import gc
import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

import etlantic as etl
from etlantic.diagnostics import Diagnostic, Severity
from etlantic.exceptions import PipelineValidationError
from etlantic.inference import (
    InferenceObservation,
    OutputProposal,
    check_write_compatibility,
    infer_records,
    inspect_target,
    inspect_target_async,
    solve_backward_constraints,
    source_factory,
    unregister_file_source,
    validate_source_binding_against_definition,
)
from etlantic.schema_drift import NormalizedField, NormalizedSchema
from etlantic.storage.protocol import records_to_dicts
from etlantic.transform.functions import (
    ceil,
    col,
    floor,
    power,
    sqrt,
    to_decimal,
    to_integer,
)


def test_provider_metadata_is_json_safe_and_python_types_are_normalized() -> None:
    class Target:
        def inspect_schema(self):
            return {
                "revision": "v1",
                "fields": [
                    {
                        "name": "id",
                        "type": int,
                        "metadata": {"provider_object": object()},
                    }
                ],
            }

    observation = inspect_target(Target())
    assert observation.schema is not None
    assert observation.schema.fields[0].logical_type == "integer"
    assert observation.revision == "v1"
    json.dumps(observation.to_dict())


def test_arbitrary_uri_target_identities_are_redacted() -> None:
    class Provider:
        def inspect_schema(self):
            return {
                "identity": "https://alice:secret@example.com/targets/orders?sig=private#fragment",
                "fields": [{"name": "id", "type": "integer"}],
            }

    observation = inspect_target(Provider())
    serialized = json.dumps(observation.to_dict(), sort_keys=True)

    assert observation.identity is not None
    assert observation.identity.startswith("target:")
    assert "alice:secret" not in serialized
    assert "sig=private" not in serialized
    assert "#fragment" not in serialized


def test_output_proposal_redacts_caller_uri_identity(tmp_path) -> None:
    identity = "https://alice:secret@example.com/targets/orders?sig=private#fragment"
    proposal = etl.from_records([{"id": 1}], name="proposal").propose_output(
        tmp_path / "missing-target",
        identity=identity,
    )

    serialized = json.dumps(proposal.to_dict(), sort_keys=True)
    assert proposal.identity.startswith("target:")
    assert identity not in serialized
    assert "alice:secret" not in serialized
    assert "sig=private" not in serialized


def test_provider_payload_bindings_participate_in_identity_collision() -> None:
    identity = "provider-payload-collision-regression"

    class Provider:
        def __init__(self, uri: str) -> None:
            self.uri = uri

        def inspect_schema(self):
            return {
                "identity": identity,
                "uri": self.uri,
                "fields": [{"name": "id", "type": "integer"}],
            }

    first = inspect_target(Provider("s3://bucket/orders-a"))
    second = inspect_target(Provider("s3://bucket/orders-b"))

    assert first.identity == identity
    assert second.exists == "unknown"
    assert "INFER_TARGET_IDENTITY_COLLISION" in {
        diagnostic.code for diagnostic in second.diagnostics
    }


def test_empty_sequence_targets_are_present_and_empty() -> None:
    observation = inspect_target([])

    assert observation.exists == "present"
    assert observation.schema is None
    assert observation.metadata["empty"] is True


@pytest.mark.parametrize("suffix", [".csv", ".json"])
def test_zero_byte_file_targets_are_present_and_empty(tmp_path, suffix: str) -> None:
    path = tmp_path / f"empty{suffix}"
    path.write_bytes(b"")

    observation = inspect_target(path)

    assert observation.exists == "present"
    assert observation.schema is None
    assert observation.metadata["empty"] is True


def test_unresolved_target_identity_survives_wire_round_trip() -> None:
    observation = inspect_target({"fields": [{"name": "id", "type": "integer"}]})
    restored = etl.TargetObservation.from_dict(observation.to_dict())

    assert observation.identity is None
    assert restored.identity is None
    assert restored.metadata["identity_unresolved"] is True
    assert restored.schema is not None
    assert "identity_unresolved" not in restored.schema.metadata
    assert restored.to_dict() == observation.to_dict()


def test_malformed_target_payloads_fail_closed_and_empty_is_explicit() -> None:
    assert inspect_target({"fields": [1]}).exists == "unknown"
    assert inspect_target({"fields": "abc"}).exists == "unknown"
    empty = inspect_target({"exists": "present", "fields": []})
    assert empty.exists == "present"
    assert empty.schema is None


def test_duplicate_fields_in_normalized_targets_fail_closed() -> None:
    target = NormalizedSchema(
        "target",
        (
            NormalizedField("id", "string"),
            NormalizedField("id", "integer"),
        ),
        {"capabilities": {"write_modes": ["append"]}},
    )

    class Provider:
        def inspect_schema(self):
            return target

    source = NormalizedSchema("source", (NormalizedField("id", "integer"),))
    for observation in (
        inspect_target(target),
        inspect_target(Provider()),
        inspect_target(etl.TargetObservation(target, "present", inspector="provided")),
    ):
        assert observation.exists == "unknown"
        assert observation.schema is None
        assert "INFER_TARGET_UNSUPPORTED" in {
            diagnostic.code for diagnostic in observation.diagnostics
        }
        assert check_write_compatibility(source, observation).status == "conflict"

    inferred = etl.infer_records_for_target(
        [{"id": 1}],
        etl.TargetObservation(target, "present", inspector="provided"),
        retain_rows=True,
    )
    assert inferred.target_observation is not None
    assert inferred.target_observation.exists == "unknown"
    assert inferred.provenance["target_validation"] == "not_performed"

    backfilled = etl.inference.backfill_schema(source, target)
    assert backfilled.schema == source
    assert "INFER_TARGET_UNSUPPORTED" in {
        diagnostic.code for diagnostic in backfilled.diagnostics
    }

    source = NormalizedSchema("source", (NormalizedField("id", "integer"),))
    malformed_observation = etl.TargetObservation(
        target,
        "present",
        metadata={"capabilities": {"write_modes": ["append"]}},
    )
    for malformed in (target, malformed_observation):
        compatibility = check_write_compatibility(source, malformed)
        assert compatibility.status == "conflict"
        assert "INFER_TARGET_UNSUPPORTED" in {
            diagnostic.code for diagnostic in compatibility.diagnostics
        }

        solved = solve_backward_constraints(source, malformed)
        assert solved.schema == source
        assert "INFER_TARGET_UNSUPPORTED" in {
            diagnostic.code for diagnostic in solved.diagnostics
        }


def test_unknown_target_types_cannot_prove_write_compatibility() -> None:
    source = NormalizedSchema("source", (NormalizedField("id", "unknown"),))
    target_schema = NormalizedSchema(
        "target",
        (NormalizedField("id", "unknown"),),
        {"capabilities": {"write_modes": ["append"]}},
    )

    for target in (
        target_schema,
        etl.TargetObservation(target_schema, "present"),
    ):
        compatibility = check_write_compatibility(source, target)
        assert compatibility.status == "conflict"
        assert "INFER_UNKNOWN_TYPE" in {
            diagnostic.code for diagnostic in compatibility.diagnostics
        }


def test_filesystem_inspection_permission_errors_fail_closed(tmp_path, monkeypatch):
    def denied_stat(_path, *args, **kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "stat", denied_stat)
    observation = inspect_target(tmp_path / "denied.csv")

    assert observation.exists == "unknown"
    assert observation.schema is None
    assert "INFER_TARGET_UNKNOWN" in {
        diagnostic.code for diagnostic in observation.diagnostics
    }


def test_filesystem_read_errors_fail_closed(tmp_path, monkeypatch):
    path = tmp_path / "unreadable.csv"
    path.write_text("id\n1\n", encoding="utf-8")

    def denied_read(*args, **kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr("etlantic.inference.targets.infer_csv", denied_read)
    observation = inspect_target(path)

    assert observation.exists == "unknown"
    assert observation.schema is None
    assert "INFER_TARGET_UNKNOWN" in {
        diagnostic.code for diagnostic in observation.diagnostics
    }


@pytest.mark.parametrize(
    "payload", [{}, {"fields": []}, {"fields": None}, {"schema": None}]
)
def test_unqualified_empty_target_payloads_are_unknown(payload) -> None:
    observation = inspect_target(payload)
    assert observation.exists == "unknown"
    assert "INFER_TARGET_UNKNOWN" in {
        diagnostic.code for diagnostic in observation.diagnostics
    }


def test_target_envelopes_do_not_become_raw_schema_mappings() -> None:
    present = inspect_target({"exists": "present"})
    assert present.exists == "present"
    assert present.schema is None
    assert present.metadata["empty"] is True

    absent = inspect_target({"exists": "absent"})
    assert absent.exists == "absent"
    assert absent.schema is None

    raw_schema = inspect_target({"revision": "INTEGER"})
    assert raw_schema.exists == "present"
    assert raw_schema.revision is None
    assert [field.name for field in raw_schema.schema.fields] == ["revision"]

    nested_schema = inspect_target({"schema": {"id": "INTEGER"}})
    assert nested_schema.exists == "present"
    assert [field.name for field in nested_schema.schema.fields] == ["id"]


def test_invalid_exists_value_is_not_reinterpreted_as_a_schema_field() -> None:
    target = {"exists": "BOOLEAN", "id": "INTEGER"}
    observation = inspect_target(target)

    assert observation.exists == "unknown"
    assert observation.schema is None
    assert "INFER_TARGET_UNKNOWN" in {
        diagnostic.code for diagnostic in observation.diagnostics
    }
    result = etl.infer_records_for_target(
        [{"exists": "true", "id": "1"}], target, retain_rows=True
    )
    assert result.provenance["target_validation"] == "not_performed"
    assert [field.logical_type for field in result.schema.fields] == [
        "string",
        "string",
    ]

    invalid_state = inspect_target({"exists": "not-a-state"})
    assert invalid_state.exists == "unknown"
    assert invalid_state.schema is None
    assert "INFER_TARGET_UNKNOWN" in {
        diagnostic.code for diagnostic in invalid_state.diagnostics
    }


def test_malformed_nested_schema_fails_closed_and_blocks_publication() -> None:
    payload = {"exists": "present", "schema": {"id": 1}}

    class SyncInspector:
        def inspect_schema(self):
            return payload

    class AsyncInspector:
        async def inspect_schema(self):
            return payload

    observations = (
        inspect_target(payload),
        inspect_target(SyncInspector()),
        asyncio.run(inspect_target_async(AsyncInspector())),
    )
    for observation in observations:
        assert observation.exists == "unknown"
        assert observation.schema is None
        assert "INFER_TARGET_UNSUPPORTED" in {
            diagnostic.code for diagnostic in observation.diagnostics
        }
        assert "INFER_TARGET_UNKNOWN" in {
            diagnostic.code for diagnostic in observation.diagnostics
        }

    dataset = etl.from_records_for_target([{"id": 1}], payload, name="orders")
    with pytest.raises(ValueError, match="inference diagnostics contain errors"):
        dataset.definition()


@pytest.mark.parametrize(
    "schema_payload",
    [
        {
            "identity": "target",
            "fields": [{"name": "id", "logical_type": "integer"}],
            "metadata": "malformed",
        },
        {
            "identity": "target",
            "fields": [
                {
                    "name": "required",
                    "logical_type": "integer",
                    "metadata": "malformed",
                }
            ],
        },
    ],
)
def test_malformed_target_wire_metadata_fails_closed(schema_payload) -> None:
    observation = etl.TargetObservation.from_dict(
        {"exists": "present", "schema": schema_payload}
    )

    assert observation.exists == "unknown"
    assert observation.schema is None
    assert "INFER_TARGET_UNSUPPORTED" in {
        diagnostic.code for diagnostic in observation.diagnostics
    }
    source = NormalizedSchema("source", (NormalizedField("id", "integer"),))
    assert check_write_compatibility(source, observation).status == "conflict"


def test_malformed_schema_less_target_metadata_fails_closed_and_serializes() -> None:
    observation = etl.TargetObservation(None, "unknown", metadata="malformed")

    assert observation.identity is None
    assert observation.metadata == {}
    assert "INFER_TARGET_UNSUPPORTED" in {
        diagnostic.code for diagnostic in observation.diagnostics
    }
    serialized = observation.to_dict()
    assert serialized["metadata"] == {}

    dataset = etl.from_records_for_target([{"id": 1}], observation)
    assert "INFER_TARGET_UNKNOWN" in {
        diagnostic.code for diagnostic in dataset.diagnostics
    }
    with pytest.raises(ValueError, match="inference diagnostics contain errors"):
        dataset.definition()


def test_provider_existence_probe_failures_fail_closed() -> None:
    class Result:
        def __init__(self):
            self.fields = [{"name": "id", "type": "integer"}]
            self.capabilities = {"write_modes": ["append"]}

        def exists(self):
            raise PermissionError("target inspection denied")

    class SyncProvider:
        def inspect_schema(self):
            return Result()

    class AsyncProvider:
        async def inspect_schema(self):
            return Result()

    observations = (
        inspect_target(SyncProvider()),
        asyncio.run(inspect_target_async(AsyncProvider())),
    )
    for observation in observations:
        assert observation.exists == "unknown"
        assert observation.schema is None
        assert "INFER_TARGET_UNKNOWN" in {
            diagnostic.code for diagnostic in observation.diagnostics
        }

    dataset = etl.from_records_for_target([{"id": 1}], SyncProvider(), name="orders")
    with pytest.raises(ValueError, match="inference diagnostics contain errors"):
        dataset.definition()


def test_async_provider_existence_probe_is_awaited() -> None:
    class Result:
        def __init__(self):
            self.fields = [{"name": "id", "type": "integer"}]

    class Provider:
        async def exists(self):
            return "present"

        async def inspect_schema(self):
            return Result()

    observation = asyncio.run(inspect_target_async(Provider()))
    assert observation.exists == "present"
    assert observation.schema is not None
    assert observation.schema.fields[0].name == "id"


def test_async_inspector_result_existence_probe_is_awaited() -> None:
    class Result:
        def __init__(self):
            self.fields = [{"name": "id", "type": "integer"}]

        async def exists(self):
            return "present"

    class Provider:
        async def exists(self):
            return "present"

        async def inspect_schema(self):
            return Result()

    observation = asyncio.run(inspect_target_async(Provider()))

    assert observation.exists == "present"
    assert observation.schema is not None
    assert observation.schema.fields[0].name == "id"


def test_async_names_target_reuses_awaited_existence_state() -> None:
    class Target:
        names = ("id",)

        def __iter__(self):
            return iter([{"name": "id", "type": "integer"}])

        async def exists(self):
            return "present"

    observation = asyncio.run(inspect_target_async(Target()))

    assert observation.exists == "present"
    assert observation.schema is not None
    assert observation.schema.fields[0].name == "id"


def test_sync_names_target_reuses_existence_probe() -> None:
    class Target:
        names = ("id",)

        def __init__(self):
            self.exists_calls = 0

        def exists(self):
            self.exists_calls += 1
            return "present"

        def __iter__(self):
            return iter([{"name": "id", "type": "integer"}])

    target = Target()
    observation = inspect_target(target)

    assert target.exists_calls == 1
    assert observation.exists == "present"
    assert observation.schema is not None
    assert observation.schema.fields[0].name == "id"


def test_sync_and_async_schema_none_fallbacks_match() -> None:
    class Target:
        schema = None
        fields = ({"name": "id", "type": "integer"},)

    sync_observation = inspect_target(Target())
    async_observation = asyncio.run(inspect_target_async(Target()))

    assert sync_observation.exists == async_observation.exists == "present"
    assert sync_observation.schema == async_observation.schema


def test_sync_and_async_inspection_use_same_provider_schema() -> None:
    class Target:
        names = ("id",)

        def __iter__(self):
            return iter([{"name": "id", "type": "string"}])

        def inspect_schema(self):
            return {"fields": [{"name": "id", "type": "integer"}]}

    sync_observation = inspect_target(Target())
    async_observation = asyncio.run(inspect_target_async(Target()))

    assert sync_observation.schema is not None
    assert async_observation.schema is not None
    assert sync_observation.schema == async_observation.schema
    assert sync_observation.schema.fields[0].logical_type == "integer"


def test_names_only_provider_unknown_types_are_diagnosed_in_both_apis() -> None:
    class Target:
        names = ("id",)

        def __iter__(self):
            return iter([{"name": "id", "type": "unsupported-type"}])

    observations = (
        inspect_target(Target()),
        asyncio.run(inspect_target_async(Target())),
    )

    for observation in observations:
        assert observation.exists == "present"
        assert observation.schema is not None
        assert observation.schema.fields[0].logical_type == "unknown"
        assert "INFER_UNKNOWN_TYPE" in {
            diagnostic.code for diagnostic in observation.diagnostics
        }


def test_async_empty_inspector_falls_back_to_schema_attribute() -> None:
    class Adapter:
        def __init__(self):
            self.schema = {"id": "INTEGER"}

        def inspect_schema(self):
            return None

    observation = asyncio.run(inspect_target_async(Adapter()))

    assert observation.exists == "present"
    assert observation.schema is not None
    assert observation.schema.fields[0].logical_type == "integer"


@pytest.mark.parametrize("exists", ["absent", "unknown"])
def test_async_direct_schema_attribute_preserves_target_existence(exists: str) -> None:
    class Adapter:
        def __init__(self):
            self.schema = {
                "exists": exists,
                "fields": [{"name": "id", "type": "integer"}],
            }

    observation = asyncio.run(inspect_target_async(Adapter()))

    assert observation.exists == exists
    assert observation.schema is None


def test_async_direct_schema_attribute_supports_normalized_and_awaitable_values() -> (
    None
):
    schema = NormalizedSchema("target", (NormalizedField("id", "integer"),))

    class NormalizedAdapter:
        def __init__(self):
            self.schema = schema

    class AwaitableAdapter:
        async def _schema(self):
            return {"id": "INTEGER"}

        def __init__(self):
            self.schema = self._schema()

    normalized = asyncio.run(inspect_target_async(NormalizedAdapter()))
    awaitable = asyncio.run(inspect_target_async(AwaitableAdapter()))

    assert normalized.exists == "present"
    assert normalized.schema == schema
    assert awaitable.exists == "present"
    assert awaitable.schema is not None
    assert awaitable.schema.fields[0].logical_type == "integer"


@pytest.mark.parametrize("async_mode", [False, True])
def test_names_provider_failures_become_unknown(async_mode: bool) -> None:
    class BrokenNames:
        exists = "present"
        names = ("id",)

        def __iter__(self):
            raise PermissionError("target rows unavailable")

    inspect = inspect_target_async if async_mode else inspect_target
    observation = (
        asyncio.run(inspect(BrokenNames())) if async_mode else inspect(BrokenNames())
    )

    assert observation.exists == "unknown"
    assert observation.schema is None
    assert "INFER_TARGET_UNKNOWN" in {
        diagnostic.code for diagnostic in observation.diagnostics
    }


def test_adapter_existence_precedes_schema_inspection() -> None:
    calls: list[str] = []

    class SyncAbsent:
        exists = "absent"

        def inspect_schema(self):
            calls.append("sync")
            return {
                "fields": [{"name": "id", "type": "integer"}],
                "capabilities": {"write_modes": ["append"]},
            }

    class SyncUnknown:
        def exists(self):
            return "unknown"

        @property
        def schema(self):
            calls.append("unknown")
            return {"fields": [{"name": "id", "type": "integer"}]}

    class AsyncAbsent:
        exists = "absent"

        async def inspect_schema(self):
            calls.append("async")
            return {"fields": [{"name": "id", "type": "integer"}]}

    sync_absent = inspect_target(SyncAbsent())
    sync_unknown = inspect_target(SyncUnknown())
    async_absent = asyncio.run(inspect_target_async(AsyncAbsent()))

    assert sync_absent.exists == "absent"
    assert sync_unknown.exists == "unknown"
    assert async_absent.exists == "absent"
    assert calls == []

    dataset = etl.from_records_for_target([{"id": 1}], SyncAbsent(), name="orders")
    with pytest.raises(ValueError, match="inference diagnostics contain errors"):
        dataset.definition()


def test_empty_inspector_result_falls_back_to_schema() -> None:
    class Adapter:
        def inspect_schema(self):
            return None

        @property
        def schema(self):
            return {"id": "INTEGER"}

    observation = inspect_target(Adapter())
    assert observation.exists == "present"
    assert observation.schema is not None
    assert observation.schema.fields[0].name == "id"


@pytest.mark.parametrize("async_mode", [False, True])
def test_provider_attribute_failures_become_unknown(async_mode: bool) -> None:
    class BadSchema:
        @property
        def schema(self):
            raise PermissionError("schema access denied")

    class BadInspector:
        @property
        def inspect_schema(self):
            raise PermissionError("inspection access denied")

    inspect = inspect_target_async if async_mode else inspect_target
    for target in (BadSchema(), BadInspector()):
        observation = asyncio.run(inspect(target)) if async_mode else inspect(target)
        assert observation.exists == "unknown"
        assert observation.schema is None
        assert "INFER_TARGET_UNKNOWN" in {
            diagnostic.code for diagnostic in observation.diagnostics
        }


def test_mapping_access_failures_become_unknown() -> None:
    class BrokenMapping(dict):
        def get(self, key, default=None):
            raise PermissionError("target mapping access denied")

    observation = inspect_target(BrokenMapping())

    assert observation.exists == "unknown"
    assert observation.schema is None
    assert "INFER_TARGET_UNKNOWN" in {
        diagnostic.code for diagnostic in observation.diagnostics
    }


@pytest.mark.parametrize("exists", ["absent", "unknown"])
def test_explicit_target_existence_precedes_schema_shape(exists: str) -> None:
    observation = inspect_target(
        {
            "exists": exists,
            "fields": [{"name": "id", "type": "integer"}],
        }
    )
    assert observation.exists == exists
    assert observation.schema is None
    assert "untrusted_schema_fingerprint" in observation.metadata


def test_explicit_empty_present_target_is_preserved() -> None:
    observation = inspect_target({"exists": "present", "fields": []})
    assert observation.exists == "present"
    assert observation.schema is None
    assert observation.metadata["empty"] is True


@pytest.mark.parametrize("exists", ["absent", "unknown"])
def test_sync_and_async_inspectors_preserve_explicit_target_existence(
    exists: str,
) -> None:
    class SyncInspector:
        def inspect_schema(self):
            return {
                "exists": exists,
                "fields": [{"name": "id", "type": "integer"}],
            }

    class AsyncInspector:
        async def inspect_schema(self):
            return {
                "exists": exists,
                "fields": [{"name": "id", "type": "integer"}],
            }

    class SyncSchema:
        def schema(self):
            return {
                "exists": exists,
                "fields": [{"name": "id", "type": "integer"}],
            }

    class AsyncSchema:
        async def schema(self):
            return {
                "exists": exists,
                "fields": [{"name": "id", "type": "integer"}],
            }

    assert inspect_target(SyncInspector()).exists == exists
    assert inspect_target(SyncSchema()).exists == exists
    assert asyncio.run(inspect_target_async(AsyncInspector())).exists == exists
    assert asyncio.run(inspect_target_async(AsyncSchema())).exists == exists


def test_invalid_target_existence_is_unknown_on_the_wire() -> None:
    for value in ("typo", "", None):
        observation = etl.TargetObservation.from_dict(
            {"exists": value, "schema": None, "metadata": {}}
        )
        assert observation.exists == "unknown"
        assert "INFER_TARGET_UNKNOWN" in {
            diagnostic.code for diagnostic in observation.diagnostics
        }

    with pytest.raises(ValueError, match="present, absent, unknown"):
        etl.TargetObservation(None, "typo")


def test_malformed_target_schema_is_unknown_on_the_wire() -> None:
    observation = etl.TargetObservation.from_dict(
        {
            "exists": "present",
            "schema": {
                "identity": "target",
                "fields": "not-a-field-list",
            },
            "metadata": {"capabilities": {"write_modes": ["append"]}},
        }
    )

    assert observation.exists == "unknown"
    assert observation.schema is None
    assert "INFER_TARGET_UNSUPPORTED" in {
        diagnostic.code for diagnostic in observation.diagnostics
    }
    source = NormalizedSchema("source", ())
    assert check_write_compatibility(source, observation).status == "conflict"


@pytest.mark.parametrize("exists", ["absent", "unknown"])
def test_malformed_wire_schema_does_not_override_explicit_nonpresent_state(
    exists: str,
) -> None:
    observation = etl.TargetObservation.from_dict(
        {
            "exists": exists,
            "schema": {"identity": "target", "fields": "malformed"},
        }
    )

    assert observation.exists == exists
    assert observation.schema is None
    assert "INFER_TARGET_UNSUPPORTED" in {
        diagnostic.code for diagnostic in observation.diagnostics
    }


@pytest.mark.parametrize("logical_type", ["unknown", "made-up"])
def test_unknown_target_logical_types_are_not_trusted_on_the_wire(
    logical_type: str,
) -> None:
    observation = etl.TargetObservation.from_dict(
        {
            "exists": "present",
            "schema": {
                "identity": "target",
                "fields": [{"name": "id", "logical_type": logical_type}],
            },
            "metadata": {"capabilities": {"write_modes": ["append"]}},
        }
    )

    assert observation.exists == "unknown"
    assert observation.schema is None
    assert "INFER_TARGET_UNSUPPORTED" in {
        diagnostic.code for diagnostic in observation.diagnostics
    }


@pytest.mark.parametrize(
    "fields",
    [
        [
            {"name": "id", "logical_type": "integer"},
            {"name": "id", "logical_type": "string"},
        ],
        [{"name": "id", "logical_type": "integer", "required": "false"}],
        [{"name": "id", "logical_type": "integer", "nullable": "false"}],
    ],
)
def test_malformed_target_field_constraints_are_not_trusted_on_the_wire(fields) -> None:
    observation = etl.TargetObservation.from_dict(
        {
            "exists": "present",
            "schema": {"identity": "target", "fields": fields},
        }
    )

    assert observation.exists == "unknown"
    assert observation.schema is None
    assert "INFER_TARGET_UNSUPPORTED" in {
        diagnostic.code for diagnostic in observation.diagnostics
    }


def test_empty_present_target_wire_payload_is_schema_less() -> None:
    observation = etl.TargetObservation.from_dict(
        {
            "exists": "present",
            "schema": {"identity": "target", "fields": []},
        }
    )

    assert observation.exists == "present"
    assert observation.schema is None
    assert observation.metadata["empty"] is True


def test_non_present_target_wire_payload_does_not_serialize_schema() -> None:
    schema = NormalizedSchema("target", (NormalizedField("id", "integer"),))
    observation = etl.TargetObservation(schema, "unknown", revision="r1")

    payload = observation.to_dict()

    assert payload["schema"] is None
    assert "untrusted_schema_fingerprint" in payload["metadata"]


@pytest.mark.parametrize("exists", ["absent", "unknown"])
def test_non_present_targets_cannot_prove_compatibility_or_backfill(
    exists: str,
) -> None:
    target_schema = NormalizedSchema("target", (NormalizedField("id", "integer"),))
    observation = etl.TargetObservation(target_schema, exists, revision="r1")
    source = NormalizedSchema("source", (NormalizedField("id", "string"),))

    compatibility = check_write_compatibility(source, observation)
    assert compatibility.status == "conflict"
    assert "INFER_TARGET_" in next(
        diagnostic.code for diagnostic in compatibility.diagnostics
    )

    result = etl.infer_records_for_target([{"id": "1"}], observation, retain_rows=True)
    assert result.schema.fields[0].logical_type == "string"
    assert result.provenance["target_validation"] == "not_performed"
    assert result.provenance["target_exists"] == exists

    solved = solve_backward_constraints(source, [observation])
    assert solved.schema.fields[0].logical_type == "string"


def test_target_inspection_error_cannot_backfill_partial_schema() -> None:
    result = etl.infer_records_for_target(
        [{"id": "7"}],
        {
            "fields": [{"name": "id", "type": "integer"}],
            "diagnostics": [{"code": "PROVIDER_READ_FAILED", "severity": "error"}],
        },
    )
    assert result.schema.fields[0].logical_type == "string"
    assert "PROVIDER_READ_FAILED" in {item.code for item in result.diagnostics}


def test_malformed_filesystem_targets_are_unknown(tmp_path) -> None:
    malformed_json = tmp_path / "target.json"
    malformed_json.write_text("{not-json", encoding="utf-8")

    observation = inspect_target(malformed_json)

    assert observation.exists == "unknown"
    assert observation.schema is None
    assert observation.diagnostics


def test_lossy_target_cast_is_not_applied_to_preview_rows() -> None:
    result = etl.infer_records_for_target(
        [{"id": 1.5}],
        {"fields": [{"name": "id", "type": "integer"}]},
        retain_rows=True,
    )
    assert result.rows == ({"id": 1.5},)
    assert result.schema.fields[0].logical_type == "number"
    assert "INFER_RUNTIME_CONVERSION" in {item.code for item in result.diagnostics}


def test_unknown_target_types_are_diagnosed() -> None:
    observation = inspect_target(
        {"fields": [{"name": "value", "type": "made_up_type"}]}
    )
    assert observation.schema is not None
    assert observation.schema.fields[0].logical_type == "unknown"
    assert "INFER_UNKNOWN_TYPE" in {item.code for item in observation.diagnostics}


def test_missing_expression_reference_is_diagnosed() -> None:
    dataset = etl.from_records([{"id": 1}]).select(col("missing").alias("value"))
    assert "INFER_LINEAGE_MISSING" in {item.code for item in dataset.diagnostics}


def test_date_datetime_promotion_and_decimal_compatibility() -> None:
    import datetime as dt
    from decimal import Decimal

    result = infer_records(
        [{"value": dt.date(2024, 1, 1)}, {"value": dt.datetime(2024, 1, 2)}]
    )
    assert result.schema.fields[0].logical_type == "datetime"
    source = NormalizedSchema("source", (NormalizedField("value", "decimal"),))
    target = NormalizedSchema("target", (NormalizedField("value", "number"),))
    assert check_write_compatibility(source, target).status == "conditional"
    assert Decimal("1.0000000000000000001")


def test_path_identities_do_not_collide_on_same_filename(tmp_path) -> None:
    left = tmp_path / "left" / "events.csv"
    right = tmp_path / "right" / "events.csv"
    left.parent.mkdir()
    right.parent.mkdir()
    left.write_text("id\n1\n", encoding="utf-8")
    right.write_text("id\n1\n", encoding="utf-8")
    assert etl.infer_csv(left).schema.identity != etl.infer_csv(right).schema.identity


def test_custom_file_identities_are_path_free(tmp_path) -> None:
    path = tmp_path / "events.csv"
    path.write_text("id\n1\n", encoding="utf-8")

    definition = etl.read_csv(str(path), name=f"dataset={path}").definition()
    payload = json.dumps(definition.to_dict())

    assert str(path) not in payload
    assert definition.nodes[0].bindings["source"]["identity"].startswith("file:")


def test_file_definition_rechecks_the_current_source_schema(tmp_path) -> None:
    path = tmp_path / "events.csv"
    path.write_text("id\n1\n", encoding="utf-8")
    dataset = etl.read_csv(path, name="events")

    path.write_text("name\nAda\n", encoding="utf-8")
    with pytest.raises(ValueError, match="INFER_SOURCE_SCHEMA_MISMATCH"):
        dataset.definition()


def test_file_definition_rejects_a_missing_source(tmp_path) -> None:
    path = tmp_path / "events.csv"
    path.write_text("id\n1\n", encoding="utf-8")
    dataset = etl.read_csv(path, name="events")
    path.unlink()

    with pytest.raises(ValueError, match="INFER_SOURCE_UNRESOLVABLE"):
        dataset.definition()


def test_target_revision_mismatch_does_not_backfill() -> None:
    result = etl.infer_records_for_target(
        [{"id": "1"}],
        {"revision": "v1", "fields": [{"name": "id", "type": "integer"}]},
        expected_revision="v2",
    )
    assert result.schema.fields[0].logical_type == "string"
    assert "INFER_TARGET_STALE" in {item.code for item in result.diagnostics}


def test_write_check_accepts_revision_aware_target_observation() -> None:
    observation = inspect_target(
        {
            "revision": "v1",
            "capabilities": {"write_modes": ["append"]},
            "fields": [{"name": "id", "type": "integer"}],
        }
    )
    source = NormalizedSchema("source", (NormalizedField("id", "integer"),))
    assert check_write_compatibility(source, observation).status == "proven"


def test_backward_solver_retains_qualified_source_constraint() -> None:
    dataset = etl.from_records([{"id": "1"}]).select(col("id").alias("value"))
    target = NormalizedSchema("target", (NormalizedField("value", "integer"),))
    result = solve_backward_constraints(dataset.schema, [target])
    assert result.schema.fields[0].logical_type == "integer"
    constraint = result.schema.metadata["backward_constraints"]["id"]
    assert constraint["observed_type"] == "string"
    assert constraint["target_type"] == "integer"


def test_output_proposal_is_explicit_and_row_free() -> None:
    proposal = etl.from_records([{"id": 1}]).propose_output(
        "/tmp/etlantic-review-target-does-not-exist.csv"
    )
    assert isinstance(proposal, OutputProposal)
    payload = proposal.to_dict()
    assert payload["create_required"] is True
    assert proposal.can_create is False
    assert "rows" not in payload
    json.dumps(payload)


def test_definition_and_plan_use_pipeline_definition() -> None:
    dataset = etl.from_records([{"id": 1}], name="users")
    definition = dataset.definition()
    assert definition.schema == "etlantic.pipeline/1"
    assert dataset.plan().pipeline_id == definition.pipeline_id


def test_one_shot_sampled_sources_cannot_be_exported_as_durable_definitions() -> None:
    dataset = etl.from_records(
        ({"id": index} for index in range(3)),
        limits=etl.InferenceLimits(max_rows=1),
    )
    with pytest.raises(ValueError, match="one-shot"):
        dataset.definition()


def test_definition_contains_each_portable_transformation_step() -> None:
    dataset = etl.from_records([{"id": "1", "amount": 2}], name="orders")
    transformed = dataset.withColumn("total", col("amount") + 1).select("id", "total")
    definition = transformed.definition()
    steps = [node for node in definition.nodes if node.kind == "step"]
    assert len(steps) == 2
    assert [step.transformation_id for step in steps] == [
        transformation.identity for transformation in definition.transformations
    ]
    assert len(definition.edges) == len(definition.nodes) - 1


def test_cumulative_schema_transfer_replays_from_root_schema() -> None:
    dataset = etl.from_records([{"id": "1", "amount": 2}], name="orders")
    transformed = dataset.withColumn("total", col("amount") + 1).rename(
        {"id": "order_id"}
    )
    assert {field.name for field in transformed.schema.fields} == {
        "order_id",
        "amount",
        "total",
    }
    assert transformed.schema.metadata["lineage_version"] == 1
    assert transformed.schema.metadata["lineage_fingerprint"]


def test_with_column_replacement_updates_lineage_without_collision() -> None:
    dataset = etl.from_records([{"id": 1, "name": "Ada"}])

    replaced = dataset.withColumn("id", col("id") + 1)

    assert replaced.collect() == [{"id": 2, "name": "Ada"}]
    assert [field.name for field in replaced.schema.fields] == ["id", "name"]
    assert "INFER_LINEAGE_COLLISION" not in {
        diagnostic.code for diagnostic in replaced.diagnostics
    }
    assert replaced.schema.metadata["lineage"]["id"]["source_fields"] == ["id"]
    assert replaced.schema.metadata["lineage"]["id"]["operations"] == ["with_fields"]


def test_with_column_appends_new_fields_and_duplicate_assignments_collide() -> None:
    dataset = etl.from_records([{"id": 1, "name": "Ada"}])
    appended = dataset.withColumn("age", 37)

    assert [field.name for field in appended.schema.fields] == ["id", "name", "age"]

    duplicate_frame = dataset.frame._extend(
        action="dtcs:with_fields",
        parameters={
            "assignments": [
                {"name": "new", "expression": {"kind": "literal", "value": 1}},
                {"name": "new", "expression": {"kind": "literal", "value": 2}},
            ]
        },
    )
    duplicate_schema = etl.forward_schema(duplicate_frame, dataset.schema)

    assert "INFER_LINEAGE_COLLISION" in {
        item["code"] for item in duplicate_schema.metadata["inference_diagnostics"]
    }


def test_mapping_record_is_inferred_as_records_not_schema() -> None:
    result = etl.infer_source({"id": 1, "name": "Ada"})
    assert [field.name for field in result.schema.fields] == ["id", "name"]


def test_target_capabilities_and_revision_are_retained_for_writes() -> None:
    observation = inspect_target(
        {
            "revision": "r1",
            "keys": ["id"],
            "capabilities": {"write_modes": ["append", "merge"]},
            "fields": [{"name": "id", "type": "integer"}],
        }
    )
    assert observation.schema is not None
    source = NormalizedSchema("source", (NormalizedField("id", "integer"),))
    assert check_write_compatibility(source, observation, mode="merge").compatible
    assert not check_write_compatibility(
        source, observation, mode="overwrite"
    ).compatible


def test_provided_target_revision_is_preserved_during_definition_export() -> None:
    target = NormalizedSchema(
        "target",
        (NormalizedField("id", "integer"),),
    )
    observation = etl.TargetObservation(
        target,
        "present",
        revision="r1",
        inspector="provided",
        metadata={"capabilities": {"write_modes": ["append"]}},
    )
    dataset = etl.from_records_for_target(
        [{"id": 1}],
        observation,
        name="revisioned_target",
        target_identity="revisioned-target",
    )

    definition = dataset.definition()

    assert definition.nodes[-1].bindings["target"]["revision"] == "r1"


def test_wire_diagnostic_round_trip_rehydrates_diagnostic() -> None:
    result = infer_records([{"id": None}])
    restored = InferenceObservation.from_dict(result.to_observation().to_dict())
    assert all(isinstance(item, Diagnostic) for item in restored.diagnostics)


def test_wire_ingress_redacts_row_like_metadata_and_preserves_target_identity() -> None:
    observation = InferenceObservation.from_dict(
        {
            "schema": {
                "identity": "source",
                "fields": [],
                "metadata": {"sampleRows": [{"id": 1}]},
            },
            "provenance": {"provider_payload": [{"id": 1}]},
        }
    )
    assert observation.schema.metadata["sampleRows"] == "<redacted>"
    assert observation.provenance["provider_payload"] == "<redacted>"
    target = etl.TargetObservation.from_dict(
        {"identity": "target-x", "exists": "present", "schema": None}
    )
    assert target.identity == "target-x"


def test_local_provider_conversion_without_head_fails_closed() -> None:
    from etlantic.dataframe.local import LocalDataframePlugin

    class Unbounded:
        def to_dicts(self):
            raise AssertionError("unbounded conversion must not run")

    result = LocalDataframePlugin().inspect_schema(Unbounded(), identity="source")
    assert result is not None
    assert result["diagnostics"][0]["code"] == "INFER_SOURCE_UNBOUNDED"


def test_provider_head_must_return_a_distinct_bounded_view() -> None:
    class Unbounded:
        def head(self, count):
            return self

        def to_dicts(self):
            raise AssertionError("self-returning head must not be materialized")

    result = etl.infer_source(Unbounded(), limits=etl.InferenceLimits(max_rows=2))
    assert "INFER_SOURCE_UNBOUNDED" in {item.code for item in result.diagnostics}


def test_provider_iterator_failure_is_a_bounded_diagnostic() -> None:
    def broken():
        yield {"id": 1}
        raise RuntimeError("provider failure")

    result = etl.infer_records(broken())
    assert result.schema.fields[0].name == "id"
    assert "INFER_SOURCE_UNSUPPORTED" in {item.code for item in result.diagnostics}


def test_invalid_csv_options_are_diagnosed(tmp_path) -> None:
    path = tmp_path / "rows.csv"
    path.write_text("id\n1\n", encoding="utf-8")
    result = etl.infer_csv(path, options=123)  # type: ignore[arg-type]
    assert "INFER_CSV_OPTIONS" in {item.code for item in result.diagnostics}


def test_jsonl_byte_limit_precedes_oversized_line_parse(tmp_path) -> None:
    path = tmp_path / "rows.jsonl"
    path.write_text('{"value":"this line is too large"}\n', encoding="utf-8")
    result = etl.infer_json(
        path, lines=True, limits=etl.InferenceLimits(max_rows=10, max_bytes=8)
    )
    assert result.schema.fields == ()
    assert "INFER_LIMIT" in {item.code for item in result.diagnostics}


def test_csv_field_limit_precedes_oversized_field_parse(tmp_path) -> None:
    path = tmp_path / "rows.csv"
    path.write_text("value\nthis value is too large\n", encoding="utf-8")
    result = etl.infer_csv(path, limits=etl.InferenceLimits(max_rows=10, max_bytes=8))
    assert result.schema.fields[0].metadata["header_only"] is True
    assert "INFER_SOURCE_UNSUPPORTED" in {item.code for item in result.diagnostics}


def test_datafusion_schema_is_metadata_first_when_installed() -> None:
    datafusion = pytest.importorskip("datafusion")
    context = datafusion.SessionContext()
    frame = context.from_pydict({"id": [1], "name": ["x"]})
    result = etl.infer_source(frame, identity="datafusion")
    assert [(field.name, field.logical_type) for field in result.schema.fields] == [
        ("id", "integer"),
        ("name", "string"),
    ]


def test_identical_observations_are_byte_stable() -> None:
    left = infer_records([{"id": 1}]).to_dict()
    right = infer_records([{"id": 1}]).to_dict()
    assert json.dumps(left, sort_keys=True, separators=(",", ":")) == json.dumps(
        right, sort_keys=True, separators=(",", ":")
    )


def test_metadata_aliases_and_paths_are_redacted() -> None:
    from etlantic.schema_drift import json_safe_metadata

    payload = json_safe_metadata(
        {
            "sampleRows": [{"secret": "row"}],
            "provider_payload": {"token": "secret"},
            "path": "/Users/example/input.csv",
        }
    )
    assert payload == {
        "sampleRows": "<redacted>",
        "provider_payload": "<redacted>",
        "path": "<path-redacted>",
    }


def test_optional_non_nullable_model_rejects_explicit_null() -> None:
    from pydantic import ValidationError

    model = etl.model_from_schema(
        NormalizedSchema(
            "optional",
            (NormalizedField("id", "integer", required=False, nullable=False),),
        )
    )
    model.model_validate({})
    with pytest.raises(ValidationError):
        model.model_validate({"id": None})


def test_target_inspector_error_fails_closed_even_with_schema() -> None:
    observation = inspect_target(
        {
            "fields": [{"name": "id", "type": "integer"}],
            "diagnostics": [
                {"code": "DENIED", "severity": "error", "message": "denied"}
            ],
        }
    )
    result = check_write_compatibility(
        NormalizedSchema("source", (NormalizedField("id", "integer"),)), observation
    )
    assert result.compatible is False
    assert "INFER_TARGET_UNKNOWN" in {item.code for item in result.diagnostics}


def test_target_observation_round_trips_into_durable_definitions() -> None:
    dataset = etl.from_records_for_target(
        [{"id": "7"}],
        {
            "revision": "r1",
            "capabilities": {"write_modes": ["append", "merge"]},
            "fields": [{"name": "id", "type": "integer"}],
        },
        name="users",
        target_identity="users-target",
    )
    observation = dataset.observation.to_dict()
    restored = InferenceObservation.from_dict(observation)
    assert restored.target_observation is not None
    assert restored.target_observation.revision == "r1"
    definition = dataset.definition().to_dict()
    assert "r1" in json.dumps(definition, sort_keys=True)
    assert "merge" in json.dumps(definition, sort_keys=True)


@pytest.mark.parametrize("severity", ["ERROR", "Warning"])
def test_any_target_diagnostic_fails_closed_and_normalizes_severity(
    severity: str,
) -> None:
    observation = inspect_target(
        {
            "fields": [{"name": "id", "type": "integer"}],
            "diagnostics": [{"code": "DENIED", "severity": severity}],
        }
    )
    assert observation.diagnostics[0].severity.value == severity.lower()
    result = etl.infer_records_for_target([{"id": "7"}], observation, retain_rows=True)
    assert result.schema.fields[0].logical_type == "string"
    assert result.target_observation == observation
    assert result.provenance["target_validation"] == "failed"
    compatibility = check_write_compatibility(
        NormalizedSchema("source", (NormalizedField("id", "integer"),)), observation
    )
    assert compatibility.compatible is False
    assert "INFER_TARGET_UNKNOWN" in {item.code for item in compatibility.diagnostics}


def test_target_diagnostics_block_schema_less_publication() -> None:
    dataset = etl.from_records_for_target(
        [{"id": 7}],
        {
            "exists": "present",
            "fields": [],
            "diagnostics": [{"code": "DENIED", "severity": "warning"}],
        },
        name="orders",
        target_identity="orders-target",
    )

    with pytest.raises(ValueError, match="INFER_TARGET_WRITE_UNQUALIFIED"):
        dataset.definition()


def test_schema_less_present_target_blocks_publication_without_diagnostics() -> None:
    dataset = etl.from_records_for_target(
        [{"id": 7}],
        {"exists": "present", "fields": []},
        name="orders",
        target_identity="orders-target",
    )

    with pytest.raises(ValueError, match="INFER_TARGET_WRITE_UNQUALIFIED"):
        dataset.definition()


def test_provided_target_diagnostics_are_not_dropped_before_publication() -> None:
    target = etl.TargetObservation(
        NormalizedSchema("target", (NormalizedField("id", "integer"),)),
        "present",
        inspector="provided",
        diagnostics=(Diagnostic("DENIED", Severity.WARNING, "target unavailable"),),
    )
    dataset = etl.from_records_for_target(
        [{"id": 7}], target, name="orders", target_identity="orders-target"
    )

    with pytest.raises(ValueError, match="INFER_TARGET_WRITE_UNQUALIFIED"):
        dataset.definition()


def test_malformed_provided_target_metadata_fails_closed_before_publication() -> None:
    target = etl.TargetObservation(
        NormalizedSchema("target", (NormalizedField("id", "integer"),)),
        "present",
        inspector="provided",
        metadata="malformed",
    )
    dataset = etl.from_records_for_target(
        [{"id": 7}], target, name="orders", target_identity="orders-target"
    )

    with pytest.raises(ValueError, match="INFER_TARGET_WRITE_UNQUALIFIED"):
        dataset.definition()


def test_revision_reader_rejects_missing_revision() -> None:
    dataset = etl.from_records_for_target(
        [{"id": 7}],
        {
            "exists": "present",
            "revision": None,
            "capabilities": {"write_modes": ["append"]},
            "fields": [{"name": "id", "type": "integer"}],
        },
        name="orders",
        target_identity="orders-target",
        revision_reader=lambda: None,
    )

    assert "INFER_TARGET_REVISION_UNKNOWN" in {
        item.code for item in dataset.diagnostics
    }
    with pytest.raises(ValueError, match="inference diagnostics contain errors"):
        dataset.definition()


def test_metadata_redaction_preserves_inference_control_values() -> None:
    from etlantic.schema_drift import json_safe_metadata

    safe = json_safe_metadata(
        {"max_rows": 2, "rows_observed": 2, "sampled": True, "sampleRows": [{"id": 1}]}
    )
    assert safe == {
        "max_rows": 2,
        "rows_observed": 2,
        "sampled": True,
        "sampleRows": "<redacted>",
    }


def test_provider_head_must_prove_conversion_bound() -> None:
    class Provider:
        def inspect_schema(self):
            return {"fields": [{"name": "id", "type": "integer"}]}

        def head(self, count):
            return View()

    class View:
        def to_dicts(self):
            return [{"id": index} for index in range(1000)]

    result = etl.infer_source(Provider(), limits=etl.InferenceLimits(max_rows=2))
    assert "INFER_SOURCE_UNBOUNDED" in {item.code for item in result.diagnostics}


def test_storage_materialization_is_bounded_by_default() -> None:
    consumed = 0

    def rows():
        nonlocal consumed
        for index in range(1000):
            consumed += 1
            yield {"id": index}

    with pytest.raises(ValueError, match="max_rows"):
        records_to_dicts(rows(), max_rows=2)
    assert consumed == 3


def test_preview_evaluator_covers_numeric_and_conversion_functions() -> None:
    dataset = etl.from_records([{"value": 9.5, "text": "9"}]).select(
        floor(col("value")).alias("floor"),
        ceil(col("value")).alias("ceil"),
        power(col("value"), 2).alias("power"),
        sqrt(col("value")).alias("sqrt"),
        to_integer(col("text")).alias("integer"),
        to_decimal(col("text")).alias("decimal"),
    )
    row = dataset.preview()[0]
    assert row["floor"] == 9
    assert row["ceil"] == 10
    assert row["power"] == 90.25
    assert row["sqrt"] == pytest.approx(3.0822, rel=1e-4)
    assert row["integer"] == 9
    assert row["decimal"] == Decimal("9")
    assert not {
        item.code
        for item in dataset.diagnostics
        if getattr(item.severity, "value", item.severity) == "error"
    }


def test_preview_evaluator_rejects_lossy_explicit_cast() -> None:
    dataset = etl.from_records([{"value": Decimal("9007199254740993")}]).withColumn(
        "converted", col("value").cast("number")
    )
    assert "INFER_RUNTIME_CONVERSION" in {item.code for item in dataset.diagnostics}


def test_schema_only_targets_do_not_invent_revisions() -> None:
    schema = NormalizedSchema("target", (NormalizedField("id", "integer"),))
    assert inspect_target(schema).revision is None

    class AsyncAdapter:
        async def schema(self):
            return schema

    assert asyncio.run(inspect_target_async(AsyncAdapter())).revision is None


def test_provider_schema_mappings_preserve_schema_and_missing_revisions() -> None:
    class SyncInspector:
        def inspect_schema(self):
            return {"id": "INTEGER"}

    class AsyncInspector:
        async def inspect_schema(self):
            return {"id": "INTEGER"}

    class SyncSchema:
        def schema(self):
            return {"id": "INTEGER"}

    class AsyncSchema:
        async def schema(self):
            return {"id": "INTEGER"}

    sync_observations = [
        inspect_target(SyncInspector()),
        inspect_target(SyncSchema()),
    ]
    async_observations = [
        asyncio.run(inspect_target_async(AsyncInspector())),
        asyncio.run(inspect_target_async(AsyncSchema())),
    ]

    for observation in (*sync_observations, *async_observations):
        assert observation.exists == "present"
        assert observation.schema is not None
        assert observation.schema.fields[0].logical_type == "integer"
        assert observation.revision is None
        json.dumps(observation.to_dict())


@pytest.mark.parametrize("async_mode", [False, True])
def test_async_and_sync_empty_provider_payloads_fail_closed(async_mode: bool) -> None:
    class Provider:
        def inspect_schema(self):
            return {"fields": None}

    target = Provider()
    if async_mode:
        observation = asyncio.run(inspect_target_async(target))
    else:
        observation = inspect_target(target)
    assert observation.exists == "unknown"
    assert "INFER_TARGET_UNKNOWN" in {
        diagnostic.code for diagnostic in observation.diagnostics
    }


def test_async_target_inspection_redacts_normalized_schema_identities() -> None:
    identity = "/Users/alice/private/target"
    schema = NormalizedSchema(identity, (NormalizedField("id", "integer"),))

    class AsyncSchema:
        async def schema(self):
            return schema

    class AsyncInspector:
        async def inspect_schema(self):
            return schema

    for target in (AsyncSchema(), AsyncInspector()):
        observation = asyncio.run(inspect_target_async(target))
        assert observation.schema is not None
        assert observation.schema.identity != identity
        assert observation.schema.identity.startswith("file:")


def test_target_guidance_does_not_replace_observed_source_contract() -> None:
    dataset = etl.from_records_for_target(
        [{"id": "1"}],
        {
            "revision": "r1",
            "capabilities": {"write_modes": ["append"]},
            "fields": [{"name": "id", "type": "integer"}],
        },
        name="orders",
        target_identity="orders-target",
    )

    definition = dataset.definition()
    source_field = definition.contracts[0].fields[0]
    assert source_field.type == "string"
    assert definition.nodes[-1].bindings["target"]["revision"] == "r1"
    assert (
        definition.nodes[-1].bindings["target"]["requirements"]["fields"][0][
            "logical_type"
        ]
        == "integer"
    )


def test_backfill_serializes_an_executable_cast_boundary() -> None:
    target = NormalizedSchema("target", (NormalizedField("id", "integer"),))
    dataset = etl.from_records([{"id": "12"}], name="orders").backfill_from(target)

    definition = dataset.definition()
    assert definition.contracts[0].fields[0].type == "string"
    assert definition.contracts[-1].fields[0].type == "integer"
    assert definition.transformations[0].portable_plan["action"] == "dtcs:with_fields"
    assert (
        definition.transformations[0].portable_plan["parameters"]["assignments"][0][
            "expression"
        ]["callee"]
        == "dtcs:cast"
    )


def test_backfill_cast_precedes_following_transformations() -> None:
    target = NormalizedSchema("target", (NormalizedField("id", "integer"),))
    dataset = etl.from_records([{"id": "12"}], name="orders").backfill_from(target)
    dataset = dataset.filter(col("id") > 0)

    definition = dataset.definition()
    assert definition.contracts[0].fields[0].type == "string"
    assert definition.contracts[-1].fields[0].type == "integer"
    assert definition.transformations[0].portable_plan["action"] == "dtcs:with_fields"
    assert definition.transformations[1].portable_plan["action"] == "dtcs:filter"


def test_materialized_definition_keeps_a_runtime_source_lease() -> None:
    definition = etl.from_records([{"id": 1}], name="temporary_definition").definition()
    restored = etl.authoring.pipeline_from_dict(definition.to_dict())

    assert etl.authoring.validate_pipeline_like(restored).valid


def test_inferred_definition_round_trips_and_plans_without_runtime_source() -> None:
    dataset = etl.from_records_for_target(
        [{"id": "1"}],
        {
            "revision": "r1",
            "capabilities": {"write_modes": ["append"]},
            "fields": [{"name": "id", "type": "integer"}],
        },
        name="orders",
        target_identity="orders-target",
    )
    restored = etl.authoring.pipeline_from_dict(dataset.definition().to_dict())
    report = etl.authoring.validate_pipeline_like(restored)
    assert report.valid
    assert etl.authoring.plan_pipeline_like(restored).pipeline_name == "orders"


def test_file_bindings_are_row_free_and_rebindable(tmp_path) -> None:
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    first.write_text("id\n1\n", encoding="utf-8")
    second.write_text("id\n2\n", encoding="utf-8")

    definition = etl.read_csv(str(first), name="events").definition()
    binding = definition.nodes[0].bindings["source"]
    assert binding["kind"] == "file"
    assert binding["uri"].startswith("file-ref:")
    definition_json = json.dumps(definition.to_dict())
    assert str(first.resolve()) not in definition_json
    assert "\n1\n" not in definition_json

    rebound = etl.rebind_definition(definition, source=str(second))
    rebound_uri = rebound.nodes[0].bindings["source"]["uri"]
    assert rebound_uri.startswith("file-ref:")
    assert rebound_uri != binding["uri"]
    assert etl.authoring.pipeline_from_dict(rebound.to_dict()).fingerprint

    resolved = etl.resolve_source_binding(binding)
    assert resolved.path == first.resolve()


def test_file_binding_options_reject_potentially_sensitive_null_values(
    tmp_path,
) -> None:
    path = tmp_path / "events.csv"
    path.write_text("id\n1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="null_values"):
        etl.read_csv(str(path), options={"null_values": ["PRIVATE_TOKEN"]}).definition()


def test_rebinding_rejects_a_source_with_a_different_schema(tmp_path) -> None:
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    first.write_text("id\n1\n", encoding="utf-8")
    second.write_text("name\nAlice\n", encoding="utf-8")

    definition = etl.read_csv(str(first), name="events").definition()
    with pytest.raises(ValueError, match="INFER_SOURCE_SCHEMA_MISMATCH"):
        etl.rebind_definition(definition, source=str(second))


def test_reloaded_file_definition_rechecks_current_schema(tmp_path) -> None:
    path = tmp_path / "events.csv"
    path.write_text("id\n1\n", encoding="utf-8")

    definition = etl.read_csv(str(path), name="events").definition()
    path.write_text("name\nAda\n", encoding="utf-8")
    restored = etl.authoring.pipeline_from_dict(definition.to_dict())

    report = etl.authoring.validate_pipeline_like(restored)
    assert not report.valid
    assert "INFER_SOURCE_SCHEMA_MISMATCH" in {item.code for item in report.errors}
    with pytest.raises(PipelineValidationError):
        etl.authoring.plan_pipeline_like(restored)


def test_file_binding_reopens_with_parser_options(tmp_path) -> None:
    path = tmp_path / "events.csv"
    path.write_text("id;name\n1;one\n", encoding="utf-8")

    dataset = etl.read_csv(
        str(path), name="semicolon_events", options={"delimiter": ";"}
    )
    reopened = etl.reopen_source_binding(
        dataset.definition().nodes[0].bindings["source"]
    )
    assert reopened.preview() == [{"id": 1, "name": "one"}]


def test_file_binding_reopens_with_inference_hints_and_limits(tmp_path) -> None:
    path = tmp_path / "events.csv"
    path.write_text("id\n1\n2\n", encoding="utf-8")

    hinted = etl.read_csv(path, hints={"id": float})
    sampled = etl.read_csv(path, limits=etl.InferenceLimits(max_rows=1))

    assert hinted.definition().contracts[0].fields[0].type == "number"
    assert sampled.definition().contracts[0].fields[0].type == "integer"


def test_file_rebinding_preserves_inference_settings(tmp_path) -> None:
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    first.write_text("id\n1\n2\n", encoding="utf-8")
    second.write_text("id\n3\n4\n", encoding="utf-8")

    dataset = etl.read_csv(
        first,
        hints={"id": float},
        limits=etl.InferenceLimits(max_rows=1),
    )
    rebound = dataset.rebind_source(str(second))

    binding = rebound.nodes[0].bindings["source"]
    assert binding["hints"] == {"id": "float"}
    assert binding["limits"]["max_rows"] == 1
    assert etl.reopen_source_binding(binding).schema.fields[0].logical_type == "number"


def test_file_binding_preserves_supported_csv_options(tmp_path) -> None:
    path = tmp_path / "events.csv"
    path.write_text("id, name\n1, Alice\n", encoding="utf-8")

    dataset = etl.read_csv(path, options={"skipinitialspace": True})
    binding = dataset.definition().nodes[0].bindings["source"]
    reopened = etl.reopen_source_binding(binding)

    assert binding["options"]["skipinitialspace"] is True
    assert reopened.preview() == dataset.preview()


def test_rebinding_preserves_valid_binding_mappings(tmp_path) -> None:
    path = tmp_path / "events.csv"
    path.write_text("id\n1\n", encoding="utf-8")

    definition = etl.read_csv(str(path), name="events").definition()
    source_binding = definition.nodes[0].bindings["source"]
    target_binding = definition.nodes[-1].bindings["target"]
    rebound = etl.rebind_definition(
        definition, source=source_binding, target=target_binding
    )

    assert rebound.nodes[0].bindings["source"]["kind"] == "file"
    assert rebound.nodes[-1].bindings["target"]["kind"] == "target"


def test_rebinding_updates_embedded_binding_metadata(tmp_path) -> None:
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    first.write_text("id\n1\n", encoding="utf-8")
    second.write_text("id\n2\n", encoding="utf-8")

    definition = etl.read_csv(str(first), name="events").definition()
    rebound = etl.rebind_definition(
        definition,
        source=str(second),
        target=definition.nodes[-1].bindings["target"],
    )
    source_binding = rebound.nodes[0].bindings["source"]
    target_binding = rebound.nodes[-1].bindings["target"]

    assert (
        rebound.nodes[0].metadata["etlantic.inference"]["source_binding"]
        == source_binding
    )
    assert (
        rebound.contracts[0].metadata["etlantic.inference"]["source_binding"]
        == source_binding
    )
    assert rebound.metadata["etlantic.inference"]["target_binding"] == target_binding
    assert (
        rebound.nodes[-1].metadata["etlantic.inference"]["target_requirements"]
        == target_binding["requirements"]
    )


def test_rebinding_rejects_an_incompatible_target() -> None:
    definition = etl.from_records([{"id": 1}], name="orders").definition()
    target_schema = NormalizedSchema("sink", (NormalizedField("id", "string"),))
    target = {
        "version": 1,
        "kind": "target",
        "identity": "sink",
        "revision": "r1",
        "write_mode": "append",
        "observed": True,
        "requirements": {
            **target_schema.to_dict(),
            "metadata": {"capabilities": {"write_modes": ["append"]}},
        },
    }

    with pytest.raises(ValueError, match="INFER_TARGET_WRITE_UNQUALIFIED"):
        etl.rebind_definition(definition, target=target)


def test_rebinding_rejects_a_target_that_needs_an_unmaterialized_cast() -> None:
    definition = etl.from_records([{"id": "1"}], name="orders").definition()
    target_schema = NormalizedSchema("sink", (NormalizedField("id", "integer"),))
    target = {
        "version": 1,
        "kind": "target",
        "identity": "sink",
        "write_mode": "append",
        "observed": True,
        "requirements": {
            **target_schema.to_dict(),
            "metadata": {"capabilities": {"write_modes": ["append"]}},
        },
    }

    with pytest.raises(ValueError, match="INFER_RUNTIME_CONVERSION"):
        etl.rebind_definition(definition, target=target)


def test_backfill_preserves_the_durable_source_binding() -> None:
    target = NormalizedSchema("target", (NormalizedField("id", "integer"),))
    dataset = etl.from_records([{"id": "12"}], name="orders").backfill_from(target)

    definition = dataset.definition()
    assert definition.nodes[0].bindings["source"]["kind"] == "records"
    assert etl.authoring.validate_pipeline_like(definition).valid


def test_reloaded_record_definition_does_not_execute_factory_during_validation() -> (
    None
):
    state = {"rows": [{"id": 1}]}
    calls: list[str] = []

    def factory():
        calls.append("called")
        return list(state["rows"])

    dataset = etl.from_records(
        state["rows"],
        name="factory_events",
        source_factory=factory,
        source_key="factory_events",
    )
    definition = dataset.definition()
    calls.clear()
    state["rows"] = [{"name": "Ada"}]
    restored = etl.authoring.pipeline_from_dict(definition.to_dict())

    report = etl.authoring.validate_pipeline_like(restored)
    assert report.valid
    assert calls == []


def test_source_binding_schema_validation_is_scoped_to_the_current_node() -> None:
    left_dataset = etl.from_records([{"id": 1}], name="left_scoped")
    right_dataset = etl.from_records([{"name": "Ada"}], name="right_scoped")
    left = left_dataset.definition()
    right = right_dataset.definition()
    combined = replace(
        left,
        contracts=left.contracts + right.contracts,
        nodes=(*left.nodes, right.nodes[0]),
    )

    validate_source_binding_against_definition(
        combined,
        left.nodes[0].bindings["source"],
        source_node=left.nodes[0],
    )


def test_transformed_file_definitions_keep_custom_identities_path_free(
    tmp_path,
) -> None:
    path = tmp_path / "events.csv"
    path.write_text("id\n1\n", encoding="utf-8")
    dataset = etl.read_csv(str(path), name=f"dataset={path}").withColumn(
        "double_id", col("id") * 2
    )

    encoded = json.dumps(dataset.definition().to_dict())
    assert str(path.resolve()) not in encoded


def test_implicit_record_snapshots_do_not_outlive_their_dataset() -> None:
    dataset = etl.from_records([{"id": 1}], name="ephemeral_snapshot")
    binding = dataset.definition().nodes[0].bindings["source"]
    assert etl.resolve_source_binding(binding) == [{"id": 1}]

    del dataset
    gc.collect()

    with pytest.raises(ValueError, match="INFER_SOURCE_UNRESOLVABLE"):
        etl.resolve_source_binding(binding)


def test_file_source_registry_can_be_released_explicitly(tmp_path) -> None:
    path = tmp_path / "events.csv"
    path.write_text("id\n1\n", encoding="utf-8")
    dataset = etl.read_csv(str(path), name="releasable_events")
    binding = dataset.definition().nodes[0].bindings["source"]

    unregister_file_source(binding["uri"])

    with pytest.raises(ValueError, match="INFER_SOURCE_UNRESOLVABLE"):
        etl.resolve_source_binding(binding)


def test_sampled_csv_with_a_file_binding_can_be_exported(tmp_path) -> None:
    path = tmp_path / "events.csv"
    path.write_text("id\n1\n2\n", encoding="utf-8")

    definition = etl.read_csv(
        str(path), limits=etl.InferenceLimits(max_rows=1)
    ).definition()
    assert definition.nodes[0].bindings["source"]["kind"] == "file"


def test_sampled_one_shot_source_can_be_explicitly_rebound(tmp_path) -> None:
    path = tmp_path / "events.csv"
    path.write_text("id\n1\n", encoding="utf-8")
    dataset = etl.from_records(
        ({"id": value} for value in (1, 2)),
        limits=etl.InferenceLimits(max_rows=1),
    )

    definition = dataset.rebind_source(str(path))
    assert definition.nodes[0].bindings["source"]["kind"] == "file"


def test_jsonl_rebinding_detects_line_format(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text('{"id": 1}\n{"id": 2}\n', encoding="utf-8")

    definition = etl.from_records([{"id": 1}], name="events").definition()
    binding = (
        etl.rebind_definition(definition, source=str(path)).nodes[0].bindings["source"]
    )
    assert binding["format"] == "jsonl"
    assert etl.reopen_source_binding(binding).preview() == [{"id": 1}, {"id": 2}]


def test_rebinding_rejects_file_sources_with_error_diagnostics(tmp_path) -> None:
    valid = tmp_path / "valid.json"
    malformed = tmp_path / "malformed.json"
    valid.write_text('[{"id": 1}]', encoding="utf-8")
    malformed.write_text('[{"id": 1}] trailing', encoding="utf-8")

    definition = etl.read_json(valid, name="events").definition()
    with pytest.raises(ValueError, match="INFER_SOURCE_REBIND"):
        etl.rebind_definition(definition, source=malformed)


def test_rebound_file_binding_lease_follows_the_binding(tmp_path) -> None:
    path = tmp_path / "events.csv"
    path.write_text("id\n1\n", encoding="utf-8")
    definition = etl.from_records([{"id": 1}], name="events").definition()

    rebound = etl.rebind_definition(definition, source=str(path))
    binding = rebound.nodes[0].bindings["source"]
    wire_binding = dict(binding)
    del rebound
    gc.collect()
    assert etl.resolve_source_binding(binding).path == path.resolve()

    del binding
    gc.collect()
    with pytest.raises(ValueError, match="INFER_SOURCE_UNRESOLVABLE"):
        etl.resolve_source_binding(wire_binding)


def test_definition_builders_preserve_file_source_leases(tmp_path) -> None:
    from etlantic.authoring.builders import replace_nodes

    path = tmp_path / "events.csv"
    path.write_text("id\n1\n", encoding="utf-8")
    original = etl.read_csv(path, name="builder_lease").definition()
    updated = replace_nodes(original, original.nodes)
    binding = updated.nodes[0].bindings["source"]

    del original
    gc.collect()

    assert etl.resolve_source_binding(binding).path == path.resolve()


def test_reopened_generator_binding_isolated_from_override() -> None:
    key = "test-reopened-generator-binding"

    def factory():
        return ({"id": value} for value in (1, 2))

    etl.register_source_factory(key, factory)
    try:
        binding = {
            "version": 1,
            "kind": "records",
            "identity": "generator",
            "resolver": "registry",
            "factory_key": key,
        }
        reopened = etl.reopen_source_binding(
            binding, limits=etl.InferenceLimits(max_rows=1)
        )
        reopened_key = reopened.definition().nodes[0].bindings["source"]["factory_key"]
        assert reopened_key != key
        assert source_factory(key) is factory
    finally:
        etl.unregister_source_factory(key)


def test_reopened_record_overrides_do_not_mutate_original_schema() -> None:
    dataset = etl.from_records([{"id": 1}], name="override_isolation")
    binding = dataset.definition().nodes[0].bindings["source"]

    reopened = etl.reopen_source_binding(binding, hints={"id": float})
    reopened_binding = reopened.definition().nodes[0].bindings["source"]

    assert reopened.schema.fields[0].logical_type == "number"
    assert reopened_binding["factory_key"] != binding["factory_key"]
    assert (
        dataset.definition().nodes[0].bindings["source"]["factory_key"]
        == (binding["factory_key"])
    )

    del dataset
    gc.collect()
    assert etl.resolve_source_binding(reopened_binding) == [{"id": 1}]

    del reopened
    gc.collect()
    assert source_factory(reopened_binding["factory_key"]) is None


def test_provider_source_can_be_explicitly_rebound(tmp_path) -> None:
    class Frame:
        def __init__(self) -> None:
            self.schema = {"id": int}

    target = tmp_path / "rebound.csv"
    target.write_text("id\n1\n", encoding="utf-8")
    definition = etl.from_pandas(Frame(), name="frame").rebind_source(str(target))
    assert definition.nodes[0].bindings["source"]["kind"] == "file"


def test_records_definition_requires_a_registered_factory() -> None:
    dataset = etl.from_records(
        ({"id": value} for value in (1, 2)), name="one_shot_records"
    )
    with pytest.raises(ValueError, match="INFER_SOURCE_UNRESOLVABLE"):
        dataset.definition()


def test_materialized_records_register_a_runtime_reopen_factory() -> None:
    dataset = etl.from_records([{"id": 1}], name="materialized_records")
    binding = dataset.definition().nodes[0].bindings["source"]
    assert etl.resolve_source_binding(binding) == [{"id": 1}]


def test_records_binding_reopens_with_inference_contract() -> None:
    dataset = etl.from_records(
        [{"id": 1}],
        name="hinted_records",
        hints={"id": float},
        limits=etl.InferenceLimits(max_rows=1),
    )
    binding = dataset.definition().nodes[0].bindings["source"]

    assert binding["hints"] == {"id": "float"}
    assert binding["limits"]["max_rows"] == 1
    reopened = etl.reopen_source_binding(binding)
    assert reopened.schema.fields[0].logical_type == "number"
    assert reopened.provenance["limits"]["max_rows"] == 1


def test_record_rebinding_rejects_hints_that_change_the_source_contract() -> None:
    definition = etl.from_records([{"id": 1}], name="hinted_rebind").definition()
    binding = dict(definition.nodes[0].bindings["source"])
    binding["hints"] = {"id": "float"}

    with pytest.raises(ValueError, match="INFER_SOURCE_SCHEMA_MISMATCH"):
        etl.rebind_definition(definition, source=binding)


def test_materialized_records_over_limits_do_not_get_an_implicit_factory() -> None:
    dataset = etl.from_records(
        [{"id": 1}, {"id": 2}],
        limits=etl.InferenceLimits(max_rows=1),
    )
    factory_key = dataset._source_binding["factory_key"]

    assert source_factory(factory_key) is None
    with pytest.raises(ValueError, match="one-shot"):
        dataset.definition()


def test_unsupported_materialized_values_fail_closed() -> None:
    class SameString:
        def __init__(self, value: int) -> None:
            self.value = value

        def __str__(self) -> str:
            return "same"

    dataset = etl.from_records(
        [{"value": SameString(1)}], name="unsupported_snapshot_value"
    )

    assert source_factory(dataset._source_binding["factory_key"]) is None
    with pytest.raises(ValueError, match="INFER_SOURCE_UNRESOLVABLE"):
        dataset.definition()


def test_default_record_pipeline_ids_are_source_specific() -> None:
    first = etl.from_records([{"id": 1}]).definition()
    second = etl.from_records([{"id": 2}]).definition()

    assert first.pipeline_id != second.pipeline_id


def test_records_bindings_do_not_alias_same_named_sources() -> None:
    first = etl.from_records([{"id": 1}], name="same_name")
    first_binding = first.definition().nodes[0].bindings["source"]
    etl.from_records([{"id": 2}], name="same_name")

    assert etl.resolve_source_binding(first_binding) == [{"id": 1}]


def test_records_bindings_preserve_value_type_distinctions() -> None:
    first = etl.from_records([{"id": Decimal("1")}], name="same_name")
    first_binding = first.definition().nodes[0].bindings["source"]
    second_binding = (
        etl.from_records([{"id": "1"}], name="same_name")
        .definition()
        .nodes[0]
        .bindings["source"]
    )

    assert first_binding != second_binding
    resolved = etl.resolve_source_binding(first_binding)
    assert isinstance(resolved[0]["id"], Decimal)


def test_missing_file_diagnostics_do_not_echo_the_source_path(tmp_path) -> None:
    path = tmp_path / "events.csv"
    path.write_text("id\n1\n", encoding="utf-8")
    definition = etl.read_csv(path, name="events").definition()
    path.unlink()

    report = etl.authoring.validate_pipeline_like(definition)
    assert not report.valid
    assert str(path) not in " ".join(item.message for item in report.errors)


def test_identical_materialized_records_have_deterministic_definitions() -> None:
    first = etl.from_records([{"id": 1}], name="same_name").definition()
    second = etl.from_records([{"id": 1}], name="same_name").definition()

    assert first.fingerprint == second.fingerprint
    assert first.nodes[0].bindings["source"] == second.nodes[0].bindings["source"]


def test_reloaded_definition_fails_closed_when_source_factory_is_missing() -> None:
    dataset = etl.from_records([{"id": 1}], name="missing_factory")
    document = dataset.definition().to_dict()
    binding = document["nodes"][0]["bindings"]["source"]
    etl.unregister_source_factory(binding["factory_key"])

    restored = etl.authoring.pipeline_from_dict(document)
    report = etl.authoring.validate_pipeline_like(restored)
    assert not report.valid
    assert "INFER_SOURCE_UNRESOLVABLE" in {item.code for item in report.errors}
    with pytest.raises(PipelineValidationError) as exc_info:
        etl.authoring.plan_pipeline_like(restored)
    assert "INFER_SOURCE_UNRESOLVABLE" in {
        item.code for item in exc_info.value.report.errors
    }


def test_target_revision_is_rechecked_before_definition() -> None:
    state = {"revision": "r1"}
    dataset = etl.from_records_for_target(
        [{"id": "1"}],
        {"revision": "r1", "fields": [{"name": "id", "type": "integer"}]},
        name="revisioned_target",
        target_identity="revisioned-target",
        revision_reader=lambda: state["revision"],
    )
    state["revision"] = "r2"

    with pytest.raises(ValueError, match="INFER_TARGET_STALE"):
        dataset.definition()


def test_target_revision_change_during_definition_is_rejected(monkeypatch) -> None:
    import etlantic.inference.facade as inference_facade

    state = {"revision": "r1"}
    dataset = etl.from_records_for_target(
        [{"id": 1}],
        {
            "revision": "r1",
            "capabilities": {"write_modes": ["append"]},
            "fields": [{"name": "id", "type": "integer"}],
        },
        name="revision_race",
        target_identity="revision-race-target",
        revision_reader=lambda: state["revision"],
    )
    check_compatibility = inference_facade.check_write_compatibility

    def change_revision_during_compatibility(*args, **kwargs):
        result = check_compatibility(*args, **kwargs)
        state["revision"] = "r2"
        return result

    monkeypatch.setattr(
        inference_facade,
        "check_write_compatibility",
        change_revision_during_compatibility,
    )

    with pytest.raises(ValueError, match="INFER_TARGET_STALE"):
        dataset.definition()


def test_malformed_csv_options_keep_the_inference_diagnostic(tmp_path) -> None:
    path = tmp_path / "events.csv"
    path.write_text("id\n1\n", encoding="utf-8")

    dataset = etl.read_csv(str(path), options=["bad"])
    with pytest.raises(ValueError, match="INFER_CSV_OPTIONS"):
        dataset.definition()


def test_rebinding_rejects_malformed_source_and_target_bindings() -> None:
    definition = etl.from_records([{"id": 1}], name="binding_shape").definition()

    with pytest.raises(ValueError, match="INFER_SOURCE_BINDING"):
        etl.rebind_definition(definition, source={"version": 1})
    with pytest.raises(ValueError, match="INFER_TARGET_BINDING"):
        etl.rebind_definition(definition, target={"version": 1})


def test_loaded_bindings_validate_parser_options_and_target_requirements(
    tmp_path,
) -> None:
    path = tmp_path / "events.csv"
    path.write_text("id\n1\n", encoding="utf-8")
    definition = etl.read_csv(path, name="events").definition()

    bad_source = {
        "version": 1,
        "kind": "file",
        "format": "csv",
        "identity": "events",
        "uri": definition.nodes[0].bindings["source"]["uri"],
        "options": {"delimiter": ["bad"]},
    }
    source_node = replace(definition.nodes[0], bindings={"source": bad_source})
    bad_source_definition = replace(
        definition,
        nodes=(source_node, *definition.nodes[1:]),
        fingerprint=None,
    ).with_fingerprint(None)
    source_report = etl.authoring.validate_pipeline_like(bad_source_definition)
    assert not source_report.valid
    assert "INFER_SOURCE_BINDING" in {item.code for item in source_report.errors}

    bad_target = {
        "version": 1,
        "kind": "target",
        "identity": "events",
        "write_mode": "append",
        "observed": True,
        "requirements": {"fields": "malformed"},
    }
    sink_node = replace(definition.nodes[-1], bindings={"target": bad_target})
    bad_target_definition = replace(
        definition,
        nodes=(*definition.nodes[:-1], sink_node),
        fingerprint=None,
    ).with_fingerprint(None)
    target_report = etl.authoring.validate_pipeline_like(bad_target_definition)
    assert not target_report.valid
    assert "INFER_TARGET_BINDING" in {item.code for item in target_report.errors}


def test_target_backfill_exports_an_explicit_cast_boundary() -> None:
    dataset = etl.from_records_for_target(
        [{"id": "1"}],
        {
            "revision": "r1",
            "capabilities": {"write_modes": ["append"]},
            "fields": [{"name": "id", "type": "integer"}],
        },
        name="orders",
        target_identity="orders-target",
    )

    definition = dataset.definition()
    assert [field.type for field in definition.contracts[0].fields] == ["string"]
    assert [field.type for field in definition.contracts[1].fields] == ["integer"]
    assert definition.transformations[0].portable_plan["parameters"]["assignments"]


def test_target_write_mode_must_be_advertised() -> None:
    dataset = etl.from_records_for_target(
        [{"id": 1}],
        {
            "revision": "r1",
            "capabilities": {"write_modes": ["merge"]},
            "keys": ["id"],
            "fields": [{"name": "id", "type": "integer"}],
        },
        name="orders",
        target_identity="orders-target",
    )

    with pytest.raises(ValueError, match="INFER_TARGET_WRITE_UNQUALIFIED"):
        dataset.definition()

    merge_dataset = etl.from_records_for_target(
        [{"id": 1}],
        {
            "revision": "r1",
            "capabilities": {"write_modes": ["merge"]},
            "keys": ["id"],
            "fields": [{"name": "id", "type": "integer"}],
        },
        name="orders",
        target_identity="orders-target",
        write_mode="merge",
    )
    assert (
        merge_dataset.definition().nodes[-1].bindings["target"]["write_mode"] == "merge"
    )


def test_invalid_target_write_mode_fails_without_a_target_schema() -> None:
    dataset = etl.from_records_for_target(
        [{"id": 1}],
        {"exists": "present", "fields": []},
        name="orders",
        target_identity="orders-target",
        write_mode="garbage",
    )

    with pytest.raises(ValueError, match="INFER_TARGET_BINDING"):
        dataset.definition()


def test_observed_target_binding_requires_normalized_requirements() -> None:
    definition = etl.from_records([{"id": 1}], name="observed_target").definition()
    bad_target = {
        "version": 1,
        "kind": "target",
        "identity": "observed_target",
        "write_mode": "append",
        "observed": True,
        "requirements": {},
    }
    sink = replace(definition.nodes[-1], bindings={"target": bad_target})
    malformed = replace(
        definition,
        nodes=(*definition.nodes[:-1], sink),
        fingerprint=None,
    ).with_fingerprint(None)

    report = etl.authoring.validate_pipeline_like(malformed)
    assert not report.valid
    assert "INFER_TARGET_BINDING" in {item.code for item in report.errors}


def test_loaded_malformed_bindings_fail_closed() -> None:
    document = etl.from_records([{"id": 1}], name="loaded_binding_shape").definition()
    payload = document.to_dict()
    payload["nodes"][0]["bindings"]["source"] = {"version": 1}
    payload["nodes"][-1]["bindings"]["target"] = {"version": 1}
    payload.pop("fingerprint")

    restored = etl.authoring.pipeline_from_dict(payload, verify=False)
    report = etl.authoring.validate_pipeline_like(restored)
    assert not report.valid
    assert {"INFER_SOURCE_BINDING", "INFER_TARGET_BINDING"} <= {
        item.code for item in report.errors
    }


def test_loaded_binding_type_errors_fail_closed() -> None:
    definition = etl.from_records([{"id": 1}], name="loaded_binding_types").definition()
    source = replace(
        definition.nodes[0],
        bindings={
            "source": {
                "version": 1,
                "kind": "file",
                "format": [],
                "uri": "file-ref:invalid",
                "options": {},
            }
        },
    )
    sink = replace(
        definition.nodes[-1],
        bindings={
            "target": {
                "version": 1,
                "kind": "target",
                "identity": "loaded_binding_types",
                "write_mode": [],
                "observed": False,
                "requirements": {},
            }
        },
    )
    malformed = replace(
        definition,
        nodes=(source, *definition.nodes[1:-1], sink),
        fingerprint=None,
    ).with_fingerprint(None)

    report = etl.authoring.validate_pipeline_like(malformed)

    assert not report.valid
    assert {"INFER_SOURCE_BINDING", "INFER_TARGET_BINDING"} <= {
        item.code for item in report.errors
    }


def test_reloaded_definition_rechecks_target_schema_compatibility() -> None:
    definition = etl.from_records([{"id": 1}], name="target_contract").definition()
    target_schema = NormalizedSchema(
        "incompatible_target", (NormalizedField("id", "string"),)
    )
    target = {
        "version": 1,
        "kind": "target",
        "identity": "incompatible_target",
        "write_mode": "append",
        "observed": True,
        "requirements": {
            **target_schema.to_dict(),
            "metadata": {"capabilities": {"write_modes": ["append"]}},
        },
    }
    sink = replace(definition.nodes[-1], bindings={"target": target})
    malformed = replace(
        definition,
        nodes=(*definition.nodes[:-1], sink),
        fingerprint=None,
    ).with_fingerprint(None)

    report = etl.authoring.validate_pipeline_like(malformed)

    assert not report.valid
    assert "INFER_TARGET_WRITE_UNQUALIFIED" in {item.code for item in report.errors}


def test_definition_rejects_a_final_target_cast_after_transformations() -> None:
    dataset = etl.from_records_for_target(
        [{"id": "12"}],
        {
            "revision": "r1",
            "capabilities": {"write_modes": ["append"]},
            "fields": [{"name": "id", "type": "integer"}],
        },
        name="orders",
        target_identity="orders-target",
    ).select(col("id").cast("string").alias("id"))

    with pytest.raises(
        ValueError,
        match=r"INFER_TARGET_WRITE_UNQUALIFIED.*INFER_RUNTIME_CONVERSION",
    ):
        dataset.definition()


def test_schema_only_target_is_a_durable_write_hypothesis() -> None:
    target = NormalizedSchema("schema_only_target", (NormalizedField("id", "integer"),))
    definition = etl.from_records_for_target(
        [{"id": 1}], target, name="schema_only_source"
    ).definition()

    assert definition.nodes[-1].bindings["target"]["observed"] is False
    assert etl.authoring.validate_pipeline_like(definition).valid


def test_file_source_registry_releases_when_dataset_is_collected(tmp_path) -> None:
    path = tmp_path / "events.csv"
    path.write_text("id\n1\n", encoding="utf-8")
    dataset = etl.read_csv(path, name="collected_events")
    binding = dataset.definition().nodes[0].bindings["source"]

    del dataset
    gc.collect()

    with pytest.raises(ValueError, match="INFER_SOURCE_UNRESOLVABLE"):
        etl.resolve_source_binding(binding)


def test_materialized_record_snapshot_isolated_from_nested_mutations() -> None:
    row = {"payload": {"value": 1}}
    dataset = etl.from_records([row], name="nested_snapshot")
    binding = dataset.definition().nodes[0].bindings["source"]

    row["payload"]["value"] = 2
    resolved = etl.resolve_source_binding(binding)
    resolved[0]["payload"]["value"] = 3

    assert etl.resolve_source_binding(binding) == [{"payload": {"value": 1}}]


def test_provided_target_binding_validates_after_reload() -> None:
    target = NormalizedSchema("provided_target", (NormalizedField("id", "integer"),))
    dataset = etl.from_records_for_target(
        [{"id": 1}],
        etl.TargetObservation(target, "present", None, "provided"),
        name="provided_target",
    )
    definition = dataset.definition()
    assert definition.nodes[-1].bindings["target"]["observed"] is False

    restored = etl.authoring.pipeline_from_dict(definition.to_dict())
    assert etl.authoring.validate_pipeline_like(restored).valid


@pytest.mark.parametrize(
    "binding",
    [
        {"kind": "s3", "uri": "s3://bucket/key"},
        {"version": 1, "kind": "s3", "uri": "s3://bucket/key"},
    ],
)
def test_lifecycle_ignores_non_durable_connector_bindings(binding) -> None:
    definition = etl.from_records([{"id": 1}], name="connector_binding").definition()
    source = replace(definition.nodes[0], bindings={"source": binding})
    connector_definition = replace(
        definition,
        nodes=(source, *definition.nodes[1:]),
        fingerprint=None,
    ).with_fingerprint(None)

    report = etl.authoring.validate_pipeline_like(connector_definition)
    assert "INFER_SOURCE_BINDING" not in {item.code for item in report.errors}


def test_unsupported_provider_does_not_look_durable() -> None:
    class Frame:
        def to_dicts(self):
            return [{"id": 1}]

        def head(self, count):
            return self

    dataset = etl.from_pandas(Frame(), name="frame")
    with pytest.raises(ValueError, match="INFER_SOURCE_UNSUPPORTED"):
        dataset.definition()


def test_path_like_source_and_target_identities_are_redacted(tmp_path) -> None:
    class Frame:
        def __init__(self) -> None:
            self.schema = {"id": int}

    rebound_path = tmp_path / "frame.csv"
    rebound_path.write_text("id\n1\n", encoding="utf-8")
    source_identity = "/Users/alice/private/frame"
    source_definition = etl.from_pandas(Frame(), name=source_identity).rebind_source(
        str(rebound_path)
    )
    assert source_identity not in json.dumps(source_definition.to_dict())

    target_identity = "/Users/alice/private/target"
    target = NormalizedSchema(target_identity, (NormalizedField("id", "integer"),))
    target_definition = etl.from_records_for_target(
        [{"id": 1}], target, name="safe_target"
    ).definition()
    assert target_identity not in json.dumps(target_definition.to_dict())


def test_missing_filter_reference_is_diagnosed() -> None:
    dataset = etl.from_records([{"id": 1}, {"id": 2}]).filter(col("missing") == 1)

    diagnostics = [
        item for item in dataset.diagnostics if item.code == "INFER_LINEAGE_MISSING"
    ]

    assert len(diagnostics) == 1
    assert diagnostics[0].path == ("missing",)
    assert dataset.collect() == []


def test_filter_reference_is_validated_after_schema_changes() -> None:
    dataset = (
        etl.from_records([{"id": 1, "name": "Ada"}])
        .rename({"id": "user_id"})
        .drop("name")
    )

    valid = dataset.filter(col("user_id") == 1)
    invalid = dataset.filter((col("user_id") == 1) & (col("name") == "Ada"))

    assert "INFER_LINEAGE_MISSING" not in {item.code for item in valid.diagnostics}
    assert "INFER_LINEAGE_MISSING" in {item.code for item in invalid.diagnostics}


def test_duplicate_missing_filter_references_are_deduplicated() -> None:
    dataset = etl.from_records([{"id": 1}]).filter(
        (col("missing") == 1) | (col("missing") == 2)
    )

    diagnostics = [
        item for item in dataset.diagnostics if item.code == "INFER_LINEAGE_MISSING"
    ]

    assert len(diagnostics) == 1


def test_nested_filter_call_references_are_diagnosed() -> None:
    dataset = etl.from_records([{"id": 1}]).filter(col("missing").isNull())

    assert "INFER_LINEAGE_MISSING" in {item.code for item in dataset.diagnostics}
