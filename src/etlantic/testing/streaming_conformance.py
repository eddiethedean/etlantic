"""Streaming and schema-registry conformance (in-memory fixtures)."""

from __future__ import annotations

from typing import Any

from etlantic.exceptions import PipelineValidationError
from etlantic.profile import Profile
from etlantic.streaming.control import ExpansionBounds, ExpansionSpec, expand_children
from etlantic.streaming.envelope import (
    ChangeEnvelopeMetadata,
    ChangeOp,
    assert_no_payload,
)
from etlantic.streaming.errors import (
    OffsetAdvanceRule,
    RecordErrorOutcome,
    RecordErrorPolicy,
)
from etlantic.streaming.fixtures import (
    InMemoryDeadLetterStore,
    InMemoryRecord,
    InMemoryStreamSource,
)
from etlantic.streaming.handoff import SnapshotCut, evaluate_handoff
from etlantic.streaming.registry import InMemorySchemaRegistry, SchemaFormat
from etlantic.streaming.trust import registry_adapter_allowed


def run_streaming_conformance_suite() -> dict[str, Any]:
    """Prove identity, bounds, DLQ no-payload, offset, and handoff fixtures."""
    checks: dict[str, bool] = {}
    spec = ExpansionSpec(
        parent_id="map-1",
        collection_identity="parts",
        bounds=ExpansionBounds(max_children=4),
    )
    children = expand_children(spec, ["a", "b"], plan_id="p", input_snapshot_id="s")
    checks["deterministic_identity"] = (
        children[0].identity
        == expand_children(spec, ["a", "b"], plan_id="p", input_snapshot_id="s")[
            0
        ].identity
    )
    try:
        expand_children(
            spec, ["a", "b", "c", "d", "e"], plan_id="p", input_snapshot_id="s"
        )
        checks["bounds"] = False
    except PipelineValidationError:
        checks["bounds"] = True

    env = ChangeEnvelopeMetadata(
        op=ChangeOp.INSERT,
        source_position="1",
        order_key="1",
        schema_identity="s",
    )
    assert_no_payload(env.to_dict())
    policy = RecordErrorPolicy(
        outcome=RecordErrorOutcome.DEAD_LETTER,
        max_retries=0,
        offset_advance=OffsetAdvanceRule.AFTER_DEAD_LETTER,
        dlq_identity="dlq:mem",
        authorization_identity="operator",
    )
    store = InMemoryDeadLetterStore(authorization_identity="operator")
    src = InMemoryStreamSource(
        identity="src",
        records=[
            InMemoryRecord(identity="ok", envelope=env, payload={"row": 1}),
            InMemoryRecord(
                identity="bad", envelope=env, payload={"row": 2}, poison=True
            ),
        ],
        policy=policy,
        dlq=store,
    )
    src.next_envelope()
    src.next_envelope()
    report = src.report_fields()
    assert_no_payload({k: str(v) for k, v in report.items() if not isinstance(v, list)})
    checks["no_payload_in_report"] = "row" not in str(report)
    meta = store.inspect_metadata(principal="operator")
    checks["dlq_metadata_only"] = all("payload" not in item for item in meta)
    try:
        store.inspect_metadata(principal="intruder")
        checks["dlq_unauthorized"] = False
    except PermissionError:
        checks["dlq_unauthorized"] = True
    first = store.redrive("bad", principal="operator")
    second = store.redrive("bad", principal="operator")
    checks["redrive_idempotent"] = first == second

    cut = SnapshotCut(
        snapshot_identity="snap",
        stream_position="10",
        schema_identity="s1",
    )
    ok = evaluate_handoff(
        snapshot=cut,
        first_stream_position="10",
        last_snapshot_position="10",
    )
    gap = evaluate_handoff(
        snapshot=cut,
        first_stream_position="11",
        last_snapshot_position="9",
    )
    checks["handoff_exact"] = ok.accepted
    checks["handoff_gap"] = gap.gap_detected and not gap.accepted
    return {
        "schema": "etlantic.streaming.conformance-report/1",
        "release": "0.46.0",
        "checks": checks,
        "passed": all(checks.values()),
    }


def run_schema_registry_conformance_suite() -> dict[str, Any]:
    """Prove identity, outage fail-closed, and production allowlist."""
    checks: dict[str, bool] = {}
    registry = InMemorySchemaRegistry()
    ident = registry.register("orders", "abc", format=SchemaFormat.JSON_SCHEMA)
    checks["register_lookup"] = (
        registry.lookup("orders").fingerprint == ident.fingerprint
    )
    registry.set_outage(True)
    try:
        registry.lookup("orders")
        checks["outage"] = False
    except LookupError:
        checks["outage"] = True
    prod = Profile(name="production", security_mode="production")
    ok, _diag = registry_adapter_allowed(prod, "etlantic-schemaregistry")
    checks["production_allowlist"] = ok is False
    pinned = Profile(
        name="production",
        security_mode="production",
        schema_registry_allowlist={"etlantic-schemaregistry": "==0.48.0"},
    )
    ok2, _ = registry_adapter_allowed(
        pinned, "etlantic-schemaregistry", version="0.48.0"
    )
    checks["production_pin"] = ok2 is True
    return {
        "schema": "etlantic.schema-registry.conformance-report/1",
        "release": "0.46.0",
        "checks": checks,
        "passed": all(checks.values()),
    }
