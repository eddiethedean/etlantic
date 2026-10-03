"""Generic adopter path for the separately installed AC056-037 provider."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from etlantic.authoring import definition_from_pipeline
from etlantic.authoring.serialize import pipeline_to_dict
from etlantic.contracts import Data
from etlantic.control_plane import (
    ControlPlaneContext,
    EnvironmentRef,
    MemoryAuthorizer,
    MemoryDefinitionRepository,
    MemoryDurableWorkStore,
    MemoryEventStore,
    MemorySubmissionStore,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic.pipeline import Extract, Load, Pipeline
from etlantic.profile import Profile
from etlantic.runtime.execution_host import ExecutionHost
from etlantic.runtime.managed_execution import ManagedExecutionAdapter
from etlantic.service import ManagedApplicationService


class Row(Data):
    event_id: str
    amount: int


class ExternalPipeline(Pipeline):
    source: Extract[Row] = Extract(asset="private-orders")
    result: Load[Row] = Load(input=source, asset="export")


workdir = Path(sys.argv[1]).resolve()
output = workdir / "managed-output.csv"
native_ref = "warehouse://tenant-a/private/orders-v3"
projection = "orders-settled/2"
profile = Profile(
    name="independent-provider-production",
    security_mode="production",
    plugin_allowlist={
        "etlantic": "==0.56.0",
        "etlantic-private-ac056037": "==1.0.0",
        "etlantic-local": "==0.50.0",
    },
    assets={
        "private-orders": {
            "provider": "private-ac056037",
            "protocol": "etlantic.source/1",
            "provider_version": "1.0.0",
            "required_capabilities": ["source.batch_snapshot"],
            "config": {
                "native_dataset_ref": native_ref,
                "projection": projection,
            },
        },
        "export": {"provider": "csv", "location": str(output)},
    },
    safe_io={"approved_roots": [str(workdir)]},
)

ctx = ControlPlaneContext(
    principal=Principal("private-provider-consumer"),
    tenant=TenantRef("tenant-a"),
    workspace=WorkspaceRef("tenant-a", "workspace-037"),
    environment=EnvironmentRef("qualification"),
    security_domain=SecurityDomain("phase-0-56"),
)
authorizer = MemoryAuthorizer()
for action in (
    "connector.catalog",
    "definition.write",
    "definition.read",
    "definition.validate",
    "definition.plan",
    "run.submit",
    "run.read",
    "run.report",
    "run.events",
    "run.lineage",
):
    authorizer.grant(ctx, action)
definitions = MemoryDefinitionRepository()
submissions = MemorySubmissionStore()
durable = MemoryDurableWorkStore()
events = MemoryEventStore()
service = ManagedApplicationService(
    authorizer=authorizer,
    definitions=definitions,
    submissions=submissions,
    durable_work=durable,
    events=events,
    profile=profile,
    report_root=workdir / "reports",
)

catalog = service.get_connector_catalog(ctx)
catalog_entry = next(
    entry for entry in catalog["connectors"] if entry["name"] == "private-ac056037"
)
assert catalog_entry["package"] == "etlantic-private-ac056037"
assert catalog_entry["package_version"] == "1.0.0"
assert catalog_entry["configuration_schema"]["required"] == [
    "native_dataset_ref",
    "projection",
]
assert catalog_entry["configuration_schema"]["properties"]["projection"]["enum"] == [
    projection
]

definition_id = "external-provider-pipeline"
service.register_definition(
    ctx,
    definition_id,
    pipeline_to_dict(definition_from_pipeline(ExternalPipeline)),
)
validation = service.validate_definition(ctx, definition_id)
assert validation["ok"], validation["diagnostics"]
planned = service.plan_definition(ctx, definition_id)
plan_binding = planned["plan"]["bindings"]["source"]
assert plan_binding["provider"] == "private-ac056037"
assert plan_binding["provider_version"] == "1.0.0"
assert plan_binding["config"]["native_dataset_ref"] == native_ref
assert plan_binding["config"]["projection"] == projection

receipt = service.submit_run(
    ctx,
    definition_id,
    idempotency_key="external-private-provider",
)
accepted = durable.get_submission(ctx, receipt.submission_id)
assert accepted.input_snapshot is not None
envelope = json.loads(accepted.input_snapshot)
accepted_binding = envelope["plan_document"]["bindings"]["source"]
assert accepted_binding["config"]["native_dataset_ref"] == native_ref
assert accepted_binding["config"]["projection"] == projection

worker = ExecutionHost(
    durable,
    owner_id="private-provider-worker",
    runner=ManagedExecutionAdapter(profile=profile, report_root=workdir / "reports"),
)
assert worker.tick(ctx) == 1
completed = durable.get_submission(ctx, receipt.submission_id)
assert completed.status == "completed"
assert output.read_text(encoding="utf-8").splitlines() == [
    "event_id,amount",
    "private-order-17,42",
]
report = service.get_run_report(ctx, str(receipt.resource_id))
assert report["status"] == "succeeded"

print(
    json.dumps(
        {
            "catalog_package": catalog_entry["package"],
            "catalog_package_version": catalog_entry["package_version"],
            "definition_id": definition_id,
            "submission_id": receipt.submission_id,
            "status": completed.status,
            "output": output.name,
            "native_reference_preserved": True,
            "projection_preserved": True,
            "provider_code_loaded_by_entry_point": True,
        },
        sort_keys=True,
    )
)
