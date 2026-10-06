# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Closed, bounded local physical boundary operations for adaptive execution."""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from anyio.to_thread import run_sync

from etlantic.dataframe.protocol import (
    ArtifactOwnership,
    DataframeExecutionContext,
    DataframeValidationOutcome,
    DataframeValidationPolicy,
)
from etlantic.exceptions import PipelineExecutionError
from etlantic.io_policy import SafeIoPolicy
from etlantic.plan.artifacts import ArtifactRef, ArtifactStrategy
from etlantic.runtime.artifacts import AttemptArtifactStore
from etlantic.storage.protocol import records_to_dicts

OPERATION_SCHEMA = "etlantic.physical_operation/1"
_FIELDS = {
    "collection": {"max_rows", "max_bytes"},
    "validation": {"port", "outcome"},
    "materialization": {"port", "checkpoint", "ttl_seconds"},
    "reuse": {"port", "checkpoint", "ttl_seconds"},
}


def validate_operation(kind: str, value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, Mapping)
        or value.get("schema") != OPERATION_SCHEMA
        or value.get("kind") != kind
    ):
        raise ValueError("A versioned physical operation descriptor is required")
    if set(value) - ({"schema", "kind"} | _FIELDS[kind]):
        raise ValueError("Physical operation contains unknown fields")
    result = dict(value)
    port = result.get("port")
    if port is not None and (not isinstance(port, str) or not port or len(port) > 128):
        raise ValueError("Boundary port must be a bounded identifier")
    if kind == "collection":
        for name in ("max_rows", "max_bytes"):
            bound = result.get(name)
            if isinstance(bound, bool) or not isinstance(bound, int) or bound < 1:
                raise ValueError("Collection requires positive finite integer bounds")
    if kind == "validation" and result.get("outcome", "fail") not in {
        "fail",
        "reject",
        "quarantine",
        "warn",
        "observe_only",
    }:
        raise ValueError("Validation outcome is unsupported")
    if kind in {"materialization", "reuse"}:
        checkpoint = result.get("checkpoint", "memory")
        if (
            not isinstance(checkpoint, str)
            or not checkpoint
            or any(
                c
                not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
                for c in checkpoint
            )
        ):
            raise ValueError("Checkpoint must be a local identifier")
        ttl = result.get("ttl_seconds")
        if ttl is not None and (
            isinstance(ttl, bool)
            or not isinstance(ttl, (int, float))
            or not math.isfinite(ttl)
            or ttl <= 0
        ):
            raise ValueError("Checkpoint retention must be finite and positive")
    return result


def _error(message: str) -> PipelineExecutionError:
    return PipelineExecutionError(message, code="PMADP520", stage="execute")


def validate_managed_resume_checkpoint(
    plan: Any, *, checkpoint_id: str, parent_run_id: str, workspace: Path
) -> str:
    """Validate that a managed checkpoint names one reusable value in this plan.

    Durable control-plane checkpoint rows contain lineage and fingerprints,
    while the checkpoint value itself remains in the scoped artifact workspace.
    The namespaced checkpoint suffix is the physical reuse boundary name.
    """
    parts = checkpoint_id.split(":")
    if len(parts) != 3 or parts[0] != "checkpoint" or parts[1] != parent_run_id:
        raise ValueError(
            "Managed resume requires this parent's checkpoint:<run-id>:<name> identity"
        )
    name = parts[2]
    if (
        not name
        or len(name) > 128
        or any(
            character
            not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
            for character in name
        )
    ):
        raise ValueError("Managed checkpoint identifier is not a local checkpoint name")
    if getattr(plan, "schema", None) != "etlantic.plan/2":
        raise ValueError("Managed resume requires a qualified adaptive plan")
    units = getattr(getattr(plan, "physical_dag", None), "units", ())
    matches: list[tuple[Any, dict[str, Any]]] = []
    for unit in units:
        metadata = getattr(unit, "metadata", {})
        requirement = (
            metadata.get("etlantic.requirement")
            if isinstance(metadata, Mapping)
            else None
        )
        if not isinstance(requirement, Mapping) or requirement.get("kind") != "reuse":
            continue
        if requirement.get("checkpoint", "memory") == name:
            matches.append((unit, validate_operation("reuse", requirement)))
    if len(matches) != 1:
        raise ValueError("Selected checkpoint must match one reusable plan boundary")
    unit, _descriptor = matches[0]
    logical_node = str(unit.metadata.get("etlantic.logical_node") or "")
    node = plan.logical_graph.node_map().get(logical_node)
    if node is None:
        raise ValueError("Selected checkpoint has no logical output")
    contract_id = _boundary_contract_id(node, _descriptor)
    path = Path(workspace) / f"checkpoint-{name}.json"
    policy = SafeIoPolicy.for_root(Path(workspace))
    records = _read_checkpoint_records(
        path,
        policy=policy,
        run_id="managed-resume-preflight",
        plan=plan,
        contract_id=contract_id,
    )
    if records is None:
        raise ValueError("Selected checkpoint value is missing, expired, or stale")
    return name


def _read_checkpoint_records(
    path: Path,
    *,
    policy: SafeIoPolicy,
    run_id: str,
    plan: Any,
    contract_id: str | None,
) -> list[Any] | None:
    from etlantic.io_policy import resolve_under_policy

    safe_path, _ = resolve_under_policy(path, policy, run_id=run_id)
    if not safe_path.exists():
        return None
    document = json.loads(safe_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or set(document) != {"metadata", "records"}:
        raise _error("Checkpoint document is malformed")
    stored = document["metadata"]
    expected_fields = {
        "schema",
        "digest",
        "producer_fingerprint",
        "contract_id",
        "security_domain",
        "created_at",
        "expires_at",
    }
    if (
        not isinstance(stored, dict)
        or set(stored) != expected_fields
        or stored.get("schema") != "etlantic.checkpoint/1"
    ):
        raise _error("Checkpoint metadata is malformed")
    for field_name in ("created_at", "expires_at"):
        timestamp = stored.get(field_name)
        if timestamp is None and field_name == "expires_at":
            continue
        if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
            raise _error("Checkpoint retention metadata is malformed")
        try:
            if not math.isfinite(float(timestamp)):
                raise _error("Checkpoint retention metadata is malformed")
        except (OverflowError, ValueError):
            raise _error("Checkpoint retention metadata is malformed") from None
    if stored["security_domain"] != plan.security_domain:
        raise _error("Checkpoint authorization mismatch")
    raw = json.dumps(
        document["records"], sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    if "sha256:" + hashlib.sha256(raw.encode()).hexdigest() != stored["digest"]:
        raise _error("Checkpoint content integrity failed")
    if (
        stored["producer_fingerprint"] != plan.fingerprint
        or stored["contract_id"] != contract_id
        or (stored["expires_at"] is not None and stored["expires_at"] <= time.time())
    ):
        return None
    decoded = json.loads(raw)
    if not isinstance(decoded, list):
        raise _error("Checkpoint records are malformed")
    return decoded


def _boundary_contract_id(node: Any, descriptor: Mapping[str, Any]) -> str | None:
    """Resolve the contract of the checkpointed output port."""
    port_name = descriptor.get("port", "result")
    for output in getattr(node, "outputs", ()):
        if getattr(output, "name", None) == port_name:
            contract_id = getattr(output, "contract_id", None)
            if isinstance(contract_id, str) and contract_id:
                return contract_id
    contract_id = getattr(node, "contract_id", None)
    return contract_id if isinstance(contract_id, str) and contract_id else None


async def execute_boundary(
    *,
    kind: str,
    unit: Any,
    node: Any,
    value: Any,
    plugin: Any,
    run_id: str,
    plan: Any,
    workspace: Path | None,
    artifacts: AttemptArtifactStore,
    artifact_key: str,
    requirement: Mapping[str, Any],
    required_checkpoint: str | None = None,
) -> tuple[Any, dict[str, Any]]:
    descriptor = validate_operation(kind, requirement)
    context = DataframeExecutionContext(
        run_id=run_id,
        pipeline_id=plan.pipeline_id,
        plan_id=plan.plan_id,
        step_name=node.name,
        engine=plugin.info.engine,
        collect=kind == "collection",
        ownership=ArtifactOwnership.COPIED,
        metadata={"physical_unit": unit.identity},
    )
    if kind == "collection":
        if isinstance(value, (list, tuple)) and len(value) > descriptor["max_rows"]:
            raise _error("Physical collection exceeds declared row bound")
        module = type(value).__module__
        if module.startswith("pandas") and len(value) > descriptor["max_rows"]:
            raise _error("Physical collection exceeds declared row bound")
        if module.startswith("polars"):
            if type(value).__name__ == "LazyFrame":
                value = cast(Any, value).limit(descriptor["max_rows"] + 1)
            elif cast(Any, value).height > descriptor["max_rows"]:
                raise _error("Physical collection exceeds declared row bound")
        collected = plugin.collect_if_needed(value, context=context)
        rows = records_to_dicts(plugin.to_records(collected, contract_type=None))
        payload = json.dumps(rows, sort_keys=True, allow_nan=False).encode()
        if len(rows) > descriptor["max_rows"] or len(payload) > descriptor["max_bytes"]:
            raise _error("Physical collection exceeds declared bounds")
        return collected, {
            "operation": "collection",
            "row_count": len(rows),
            "byte_count": len(payload),
        }
    if kind == "validation":
        outcome = DataframeValidationOutcome(descriptor.get("outcome", "fail"))
        context = replace(
            context, validation_policy=DataframeValidationPolicy(output_outcome=outcome)
        )
        validated, decision, _diagnostics, invalid = plugin.validate_frame(
            value,
            contract_type=node.contract_type,
            context=context,
            boundary="output_validation",
            port_name=descriptor.get("port", "result"),
        )
        if str(getattr(decision, "value", decision)) == "failed":
            raise _error("Physical contract validation failed")
        if invalid is not None:
            rejected_ref = ArtifactRef(
                identity=f"rejected:{run_id}:{unit.identity}",
                logical_output=artifact_key + "#invalid",
                strategy=ArtifactStrategy.IN_MEMORY,
                security_domain=plan.security_domain,
            )
            artifacts.put(rejected_ref, invalid, durable=False, ownership="copied")
        return validated, {"operation": "validation", "decision": decision.value}
    records = records_to_dicts(
        plugin.to_records(value, contract_type=node.contract_type)
    )
    payload = json.dumps(
        records, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    digest = "sha256:" + hashlib.sha256(payload.encode()).hexdigest()
    checkpoint = descriptor.get("checkpoint", "memory")
    identity = hashlib.sha256(
        f"{plan.fingerprint}:{unit.identity}:{checkpoint}".encode()
    ).hexdigest()
    ref = ArtifactRef(
        identity=f"checkpoint:{run_id}:{identity[:24]}",
        logical_output=artifact_key,
        strategy=ArtifactStrategy.IN_MEMORY,
        security_domain=plan.security_domain,
    )
    if checkpoint == "memory":
        copied = plugin.ensure_ownership(
            value, ownership=ArtifactOwnership.COPIED, context=context
        )
        artifacts.put(ref, copied, durable=False, ownership="copied")
        return copied, {"operation": kind, "checkpoint": checkpoint, "digest": digest}
    if workspace is None:
        raise _error("Named physical checkpoints require a workspace")
    path = Path(workspace) / f"checkpoint-{checkpoint}.json"
    policy = artifacts.policy or SafeIoPolicy.for_root(Path(workspace))
    now = time.time()
    metadata = {
        "schema": "etlantic.checkpoint/1",
        "digest": digest,
        "producer_fingerprint": plan.fingerprint,
        "contract_id": _boundary_contract_id(node, descriptor),
        "security_domain": plan.security_domain,
        "created_at": now,
        "expires_at": now + descriptor["ttl_seconds"]
        if descriptor.get("ttl_seconds")
        else None,
    }
    if kind == "materialization" and required_checkpoint == checkpoint:
        # A resume may pass through the original materialization boundary
        # before its reuse boundary. Keep the selected parent value immutable
        # so the following reuse cannot accidentally read this attempt's value.
        artifacts.put(ref, value, durable=False, ownership="copied")
        return value, {
            "operation": "checkpoint",
            "checkpoint": checkpoint,
            "selection": "preserved_for_resume",
        }
    if kind == "reuse":

        def read_checkpoint() -> Any:
            decoded = _read_checkpoint_records(
                path,
                policy=policy,
                run_id=run_id,
                plan=plan,
                contract_id=_boundary_contract_id(node, descriptor),
            )
            if decoded is None:
                return None
            return plugin.materialize_input(
                decoded,
                contract_type=node.contract_type,
                context=context,
                port_name=descriptor.get("port", "result"),
            )

        reused = await run_sync(read_checkpoint)
        if required_checkpoint == checkpoint and reused is None:
            raise _error("Selected managed checkpoint is no longer restorable")
        selected = value if reused is None else reused
        artifacts.put(ref, selected, durable=False, ownership="copied")
        return selected, {
            "operation": "reuse",
            "selection": "producer" if reused is None else "checkpoint",
            "checkpoint": checkpoint,
        }

    artifacts.stage_text(
        path,
        json.dumps(
            {"metadata": metadata, "records": records},
            sort_keys=True,
            allow_nan=False,
        ),
        policy,
        run_id=run_id,
    )
    artifacts.put(ref, value, durable=False, ownership="copied")
    return value, {
        "operation": "checkpoint",
        "checkpoint": checkpoint,
        "digest": digest,
    }
