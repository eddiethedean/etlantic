#!/usr/bin/env python3
"""Fail-closed public-control coverage inventory for phase 0.56.

The inventory is generated from the shipped CP OpenAPI contract. Each
operation is attached to a storage authority and a runtime consumer (or an
explicit statement that the operation has no ETL runtime effect). Every
parameter and request/response schema field is recorded so a new, removed, or
downgraded control cannot silently fall outside qualification.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

from fastapi.routing import APIRoute

from etlantic.control_plane.memory import (
    MemoryAuthorizer,
    MemoryDefinitionRepository,
    MemoryEventStore,
    MemorySubmissionStore,
)
from etlantic_fastapi.api import ETLanticAPI
from etlantic_fastapi.auth import static_context_factory
from fastapi import FastAPI

ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = (
    ROOT / "docs/11_DEVELOPMENT/evidence/phase_0_56/PUBLIC_CONTROL_COVERAGE_0_56.json"
)


def _as_mapping(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return cast(dict[str, Any], value)


def _as_list(value: object) -> list[Any]:
    if not isinstance(value, list):
        return []
    return cast(list[Any], value)


# Public for the companion authorization campaign, which walks the same
# generated OpenAPI document with the same schema narrowing rules.
as_mapping = _as_mapping
as_list = _as_list


def _anchor(path: str, symbol: str) -> dict[str, str]:
    return {"path": path, "symbol": symbol}


# A flow is deliberately attached by OpenAPI tag, not inferred from route
# implementation details. Keeping every tag explicit makes new route families
# fail closed until their ownership and effect path are reviewed.
FLOWS: dict[str, dict[str, Any]] = {
    "input-resources": {
        "storage_mode": "durable-resource-store",
        "storage_anchor": _anchor(
            "src/etlantic/control_plane/input_resources.py", "class InputResourceStore"
        ),
        "runtime_anchor": _anchor(
            "src/etlantic/runtime/managed_execution.py", "class ManagedExecutionAdapter"
        ),
        "evidence_tests": [
            "tests/control_plane/test_input_resources_0_56.py",
            "tests/fastapi/test_managed_backend_0_56.py",
        ],
    },
    "operability": {
        "storage_mode": "readiness-composition-state",
        "storage_anchor": _anchor(
            "packages/etlantic-fastapi/src/etlantic_fastapi/api.py", "def stores_ready"
        ),
        "runtime_exclusion_reason": "Health and readiness report composition state and never enqueue ETL work.",
        "evidence_tests": ["tests/fastapi/test_cp1_openapi.py"],
    },
    "definitions": {
        "storage_mode": "definition-repository",
        "storage_anchor": _anchor(
            "src/etlantic/control_plane/protocols.py", "class DefinitionRepository"
        ),
        "runtime_anchor": _anchor(
            "src/etlantic/service/managed.py", "class ManagedApplicationService"
        ),
        "evidence_tests": ["tests/fastapi/test_managed_application_0_56.py"],
    },
    "catalog": {
        "storage_mode": "derived-from-installed-provider-metadata",
        "storage_anchor": _anchor(
            "src/etlantic/connectors/catalog.py", "def connector_catalog_for_profile"
        ),
        "runtime_anchor": _anchor("src/etlantic/registry.py", "class PlanningContext"),
        "evidence_tests": [
            "tests/connectors/test_connector_catalog_0_56.py",
            "tests/connectors/test_connector_configuration_schemas_0_56.py",
        ],
    },
    "connector-actions": {
        "storage_mode": "durable-action-job-store",
        "storage_anchor": _anchor(
            "src/etlantic/control_plane/durable_protocols.py", "class DurableWorkStore"
        ),
        "runtime_anchor": _anchor(
            "src/etlantic/runtime/action_execution_host.py", "class ActionExecutionHost"
        ),
        "evidence_tests": [
            "tests/control_plane/test_action_jobs_0_56.py",
            "tests/fastapi/test_managed_action_jobs_0_56.py",
        ],
    },
    "runs": {
        "storage_mode": "durable-submission-and-result-stores",
        "storage_anchor": _anchor(
            "src/etlantic/control_plane/durable_protocols.py", "class DurableWorkStore"
        ),
        "runtime_anchor": _anchor(
            "src/etlantic/runtime/managed_execution.py", "class ManagedExecutionAdapter"
        ),
        "evidence_tests": [
            "tests/fastapi/test_managed_application_0_56.py",
            "tests/fastapi/test_managed_backend_0_56.py",
        ],
    },
    "schema": {
        "storage_mode": "scoped-schema-history-store",
        "storage_anchor": _anchor(
            "src/etlantic/control_plane/history_protocols.py", "class HistoryStore"
        ),
        "runtime_anchor": _anchor(
            "src/etlantic/service/managed.py", "class ManagedApplicationService"
        ),
        "evidence_tests": [
            "tests/control_plane/test_history_0_40.py",
            "tests/fastapi/test_cp1_full_authz_matrix.py",
        ],
    },
    "reliability": {
        "storage_mode": "scoped-reliability-history-store",
        "storage_anchor": _anchor(
            "src/etlantic/control_plane/history_protocols.py", "class HistoryStore"
        ),
        "runtime_exclusion_reason": "Reliability endpoints read persisted evidence and do not start ETL work.",
        "evidence_tests": ["tests/reliability/test_reliability.py"],
    },
    "registry": {
        "storage_mode": "revision-and-alias-registry",
        "storage_anchor": _anchor(
            "src/etlantic/control_plane/registry_protocols.py", "class RegistryProvider"
        ),
        "runtime_anchor": _anchor(
            "src/etlantic/control_plane/registry_definitions.py",
            "class RegistryDefinitionRepository",
        ),
        "evidence_tests": [
            "tests/control_plane/test_registry_0_40.py",
            "tests/fastapi/test_cp1_registry_routes_0_40.py",
        ],
    },
    "durable": {
        "storage_mode": "durable-work-store",
        "storage_anchor": _anchor(
            "src/etlantic/control_plane/durable_protocols.py", "class DurableWorkStore"
        ),
        "runtime_anchor": _anchor(
            "src/etlantic/runtime/execution_host.py", "class ExecutionHost"
        ),
        "evidence_tests": [
            "tests/control_plane/test_durable_work_0_41.py",
            "tests/fastapi/test_durable_routes_0_41.py",
        ],
    },
    "policy": {
        "storage_mode": "policy-provider",
        "storage_anchor": _anchor(
            "src/etlantic/control_plane/policy_protocols.py", "class PolicyProvider"
        ),
        "runtime_anchor": _anchor(
            "src/etlantic/service/managed.py", "def _accept_durable"
        ),
        "evidence_tests": ["tests/control_plane/test_policy_0_42.py"],
    },
    "approvals": {
        "storage_mode": "approval-store",
        "storage_anchor": _anchor(
            "src/etlantic/control_plane/approval_protocols.py", "class ApprovalStore"
        ),
        "runtime_anchor": _anchor(
            "src/etlantic/service/managed.py", "def _accept_durable"
        ),
        "evidence_tests": ["tests/fastapi/test_cp1_full_authz_matrix.py"],
    },
    "quotas": {
        "storage_mode": "quota-provider",
        "storage_anchor": _anchor(
            "src/etlantic/control_plane/quota_protocols.py", "class QuotaProvider"
        ),
        "runtime_anchor": _anchor(
            "src/etlantic/service/managed.py", "def _accept_durable"
        ),
        "evidence_tests": ["tests/fastapi/test_managed_application_0_56.py"],
    },
    "erasure": {
        "storage_mode": "scoped-erasure-store",
        "storage_anchor": _anchor(
            "src/etlantic/control_plane/erasure_protocols.py", "class ErasureStore"
        ),
        "runtime_exclusion_reason": "Erasure planning and execution operate on scoped control-plane evidence, not ETL submissions.",
        "evidence_tests": ["tests/fastapi/test_cp1_full_authz_matrix.py"],
    },
    "audit": {
        "storage_mode": "scoped-audit-evidence-store",
        "storage_anchor": _anchor(
            "src/etlantic/control_plane/audit_protocols.py", "class AuditEvidenceStore"
        ),
        "runtime_exclusion_reason": "Audit queries and exports read control-plane evidence and do not start ETL work.",
        "evidence_tests": ["tests/fastapi/test_cp1_full_authz_matrix.py"],
    },
    "attestations": {
        "storage_mode": "scoped-attestation-store",
        "storage_anchor": _anchor(
            "src/etlantic/control_plane/attestation_protocols.py",
            "class AttestationStore",
        ),
        "runtime_anchor": _anchor(
            "src/etlantic/service/managed.py", "def _accept_durable"
        ),
        "evidence_tests": ["tests/fastapi/test_cp1_full_authz_matrix.py"],
    },
    "objectives": {
        "storage_mode": "scoped-objective-store",
        "storage_anchor": _anchor(
            "src/etlantic/control_plane/objective_protocols.py", "class ObjectiveStore"
        ),
        "runtime_exclusion_reason": "Objective evaluation is an external business control and does not execute ETL.",
        "evidence_tests": ["tests/fastapi/test_cp1_full_authz_matrix.py"],
    },
    "schedules": {
        "storage_mode": "scoped-schedule-store",
        "storage_anchor": _anchor(
            "src/etlantic/control_plane/schedule_protocols.py", "class ScheduleStore"
        ),
        "runtime_anchor": _anchor(
            "src/etlantic/runtime/scheduler_service.py", "class SchedulerService"
        ),
        "evidence_tests": [
            "tests/schedule/test_firing_scope.py",
            "tests/fastapi/test_schedule_routes_0_47.py",
        ],
    },
    "intelligence": {
        "storage_mode": "derived-from-definition-and-planning-context",
        "storage_anchor": _anchor(
            "src/etlantic/service/managed.py", "class ManagedApplicationService"
        ),
        "runtime_anchor": _anchor("src/etlantic/registry.py", "class PlanningContext"),
        "evidence_tests": ["tests/fastapi/test_cp1_openapi.py"],
    },
}


def _schema_fields(
    schema: dict[str, Any],
    components: dict[str, Any],
    *,
    prefix: str = "",
    seen: frozenset[str] = frozenset(),
) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    ref = schema.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
        name = ref.rsplit("/", 1)[-1]
        if name in seen:
            return fields
        fields.extend(
            _schema_fields(
                components.get(name, {}), components, prefix=prefix, seen=seen | {name}
            )
        )
        return fields

    for variant_key in ("allOf", "anyOf", "oneOf"):
        for index, raw_variant in enumerate(_as_list(schema.get(variant_key))):
            variant = _as_mapping(raw_variant)
            if variant:
                fields.extend(
                    _schema_fields(
                        variant,
                        components,
                        prefix=f"{prefix}<{variant_key}:{index}>",
                        seen=seen,
                    )
                )

    properties = _as_mapping(schema.get("properties"))
    required = set(_as_list(schema.get("required")))
    if properties:
        for name, prop in properties.items():
            prop = _as_mapping(prop)
            path = f"{prefix}.{name}" if prefix else str(name)
            fields.append(
                {
                    "path": path,
                    "required": name in required,
                    "type": prop.get("type", "ref" if "$ref" in prop else "object"),
                }
            )
            fields.extend(_schema_fields(prop, components, prefix=path, seen=seen))
    elif schema.get("items") is not None:
        fields.extend(
            _schema_fields(
                _as_mapping(schema["items"]),
                components,
                prefix=f"{prefix}[]",
                seen=seen,
            )
        )
    additional = _as_mapping(schema.get("additionalProperties"))
    if additional:
        fields.append(
            {
                "path": f"{prefix}.*" if prefix else "*",
                "required": False,
                "type": "dynamic-map-value",
            }
        )
        fields.extend(
            _schema_fields(additional, components, prefix=f"{prefix}.*", seen=seen)
        )
    return fields


def _operation_fields(
    operation: dict[str, Any], components: dict[str, Any]
) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    for raw_parameter in _as_list(operation.get("parameters", [])):
        parameter = _as_mapping(raw_parameter)
        if not parameter:
            continue
        fields.append(
            {
                "surface": "parameter",
                "location": parameter.get("in", "unknown"),
                "path": parameter.get("name", ""),
                "required": bool(parameter.get("required", False)),
                "type": _as_mapping(parameter.get("schema")).get("type", "unknown"),
            }
        )
    request_body = _as_mapping(operation.get("requestBody", {}))
    for media_type, raw_content in _as_mapping(request_body.get("content", {})).items():
        content = _as_mapping(raw_content)
        fields.extend(
            {
                "surface": "request",
                "media_type": media_type,
                **field,
            }
            for field in _schema_fields(content.get("schema", {}), components)
        )
    for status_code, raw_response in _as_mapping(
        operation.get("responses", {})
    ).items():
        response = _as_mapping(raw_response)
        for media_type, raw_content in _as_mapping(response.get("content", {})).items():
            content = _as_mapping(raw_content)
            fields.extend(
                {
                    "surface": "response",
                    "status_code": str(status_code),
                    "media_type": media_type,
                    **field,
                }
                for field in _schema_fields(content.get("schema", {}), components)
            )
    return sorted(
        fields,
        key=lambda item: (
            item["surface"],
            item.get("location", ""),
            item.get("status_code", ""),
            item.get("media_type", ""),
            item["path"],
        ),
    )


def build_openapi() -> tuple[dict[str, Any], dict[str, str]]:
    """Construct the public CP schema without starting stores or a worker."""
    api = ETLanticAPI(
        authorizer=MemoryAuthorizer(),
        definitions=MemoryDefinitionRepository(),
        submissions=MemorySubmissionStore(),
        events=MemoryEventStore(),
        context_factory=static_context_factory(
            tenant_id="coverage-inventory", workspace_id="coverage-inventory"
        ),
    )
    app = FastAPI()
    app.include_router(api.router)
    endpoint_names: dict[str, str] = {}
    for route in api.router.routes:
        if isinstance(route, APIRoute) and route.operation_id:
            endpoint_names[route.operation_id] = route.endpoint.__name__
    return app.openapi(), endpoint_names


def build_inventory() -> dict[str, Any]:
    openapi, endpoint_names = build_openapi()
    components = _as_mapping(
        _as_mapping(openapi.get("components", {})).get("schemas", {})
    )
    operations: list[dict[str, Any]] = []
    for path, raw_methods in _as_mapping(openapi.get("paths", {})).items():
        for method, raw_operation in _as_mapping(raw_methods).items():
            operation = _as_mapping(raw_operation)
            operation_id = operation.get("operationId", "")
            if not operation_id.startswith("cp_"):
                continue
            tags = operation.get("tags", [])
            tag = tags[0] if tags else ""
            if tag not in FLOWS:
                raise ValueError(
                    f"No phase 0.56 coverage flow for {operation_id} ({tag})"
                )
            operations.append(
                {
                    "operation_id": operation_id,
                    "method": method.upper(),
                    "path": path,
                    "tag": tag,
                    "kind": "query" if method.lower() == "get" else "command",
                    "handler": endpoint_names.get(operation_id, ""),
                    "coverage": "mapped",
                    "fields": _operation_fields(operation, components),
                }
            )
    operations.sort(key=lambda item: item["operation_id"])
    return {
        "schema": "etlantic.phase_0_56.public_control_coverage/1",
        "scope": "Every CP OpenAPI operation, parameter, and typed request/response field.",
        "flow_contract": "Each operation inherits the storage and runtime trace attached to its OpenAPI tag. A runtime exclusion is explicit for controls that have no ETL execution effect.",
        "flows": FLOWS,
        "operations": operations,
    }


def validate_inventory(inventory: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected = build_inventory()
    if inventory.get("schema") != expected["schema"]:
        errors.append("coverage schema identifier is missing or unsupported")
    flows = _as_mapping(inventory.get("flows"))
    if not flows or flows != FLOWS:
        errors.append("storage/runtime flow ownership differs from the reviewed map")

    actual_operations = inventory.get("operations")
    expected_operations = expected["operations"]
    if not isinstance(actual_operations, list):
        errors.append("operations must be a list")
        operation_rows: list[Any] = []
    else:
        operation_rows = cast(list[Any], actual_operations)
    actual_by_id: dict[str, dict[str, Any]] = {}
    for raw_row in operation_rows:
        row = _as_mapping(raw_row)
        if not isinstance(row.get("operation_id"), str):
            errors.append("each operation needs a stable operation_id")
            continue
        operation_id = row["operation_id"]
        if operation_id in actual_by_id:
            errors.append(f"duplicate operation row: {operation_id}")
        actual_by_id[operation_id] = row

    expected_by_id = {row["operation_id"]: row for row in expected_operations}
    if set(actual_by_id) != set(expected_by_id):
        missing = sorted(set(expected_by_id) - set(actual_by_id))
        extra = sorted(set(actual_by_id) - set(expected_by_id))
        if missing:
            errors.append("unmapped public operations: " + ", ".join(missing))
        if extra:
            errors.append("unknown public operations: " + ", ".join(extra))

    for operation_id, expected_row in expected_by_id.items():
        row = actual_by_id.get(operation_id)
        if row is None:
            continue
        for key in ("method", "path", "tag", "kind", "handler", "fields"):
            if row.get(key) != expected_row.get(key):
                errors.append(f"{operation_id}: {key} is stale or incomplete")
        if row.get("coverage") != "mapped":
            errors.append(f"{operation_id}: coverage may not be downgraded")
        tag_value = row.get("tag")
        if not isinstance(tag_value, str):
            errors.append(f"{operation_id}: malformed flow tag")
            continue
        flow = _as_mapping(flows.get(tag_value, {}))
        if not flow:
            errors.append(f"{operation_id}: missing storage/runtime flow")

    for raw_tag, raw_flow in flows.items():
        tag = str(raw_tag)
        flow = _as_mapping(raw_flow)
        if tag not in {row["tag"] for row in expected_operations}:
            errors.append(f"orphan flow entry: {tag}")
            continue
        storage_anchor = flow.get("storage_anchor")
        if not isinstance(storage_anchor, dict):
            errors.append(f"{tag}: missing storage authority anchor")
        else:
            errors.extend(
                _validate_anchor(tag, "storage", cast(dict[str, Any], storage_anchor))
            )
        runtime_anchor = flow.get("runtime_anchor")
        if isinstance(runtime_anchor, dict):
            errors.extend(
                _validate_anchor(tag, "runtime", cast(dict[str, Any], runtime_anchor))
            )
        elif (
            not isinstance(flow.get("runtime_exclusion_reason"), str)
            or not flow["runtime_exclusion_reason"].strip()
        ):
            errors.append(f"{tag}: missing runtime anchor or explicit exclusion")
        tests = _as_list(flow.get("evidence_tests"))
        if not tests:
            errors.append(f"{tag}: missing evidence test modules")
        else:
            for test_value in tests:
                if not isinstance(test_value, str):
                    errors.append(f"{tag}: malformed evidence test path")
                    continue
                if not (ROOT / test_value).is_file():
                    errors.append(f"{tag}: evidence test does not exist: {test_value}")
    return errors


def _validate_anchor(tag: str, layer: str, anchor: dict[str, Any]) -> list[str]:
    path = anchor.get("path")
    symbol = anchor.get("symbol")
    if not isinstance(path, str) or not isinstance(symbol, str):
        return [f"{tag}: malformed {layer} anchor"]
    source = ROOT / path
    if not source.is_file():
        return [f"{tag}: {layer} anchor path does not exist: {path}"]
    if symbol not in source.read_text(encoding="utf-8"):
        return [f"{tag}: {layer} anchor symbol not found: {path}::{symbol}"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="Regenerate the public operation/field rows from the current OpenAPI contract.",
    )
    args = parser.parse_args()
    inventory = build_inventory()
    if args.write:
        INVENTORY_PATH.write_text(
            json.dumps(inventory, indent=2, sort_keys=False) + "\n", encoding="utf-8"
        )
    if args.write:
        errors = validate_inventory(inventory)
        if not errors:
            INVENTORY_PATH.write_text(
                json.dumps(inventory, indent=2, sort_keys=False) + "\n",
                encoding="utf-8",
            )
    else:
        errors = validate_inventory(
            json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
        )
    if errors:
        print("phase 0.56 public control coverage FAILED:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(
        "phase 0.56 public control coverage passed "
        f"({len(inventory['operations'])} operations, "
        f"{sum(len(row['fields']) for row in inventory['operations'])} "
        "parameter/schema fields)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
