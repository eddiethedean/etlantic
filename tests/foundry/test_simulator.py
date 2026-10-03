from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import anyio
import httpx2
import pytest
from etlantic_foundry.action_handlers import create_action_handlers
from etlantic_foundry.connectors import (
    FoundrySinkConnector,
    FoundrySourceConnector,
    FoundryStorageConnector,
)
from tests.foundry.simulator import (
    FOUNDRY_DATASET,
    FOUNDRY_TOKEN,
    PINNED_TRANSACTION,
    FoundrySimulator,
)

from etlantic import Data, Extract, Load, Pipeline, PipelineRuntime, Profile
from etlantic.connectors.errors import ConnectorConfigError, ConnectorReadError
from etlantic.connectors.models import CommitReceipt
from etlantic.connectors.session import write_via_sink_connector
from etlantic.control_plane import (
    ControlPlaneContext,
    EnvironmentRef,
    MemoryAuthorizer,
    MemoryDurableWorkStore,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic.registry import BindingDescriptor, PlanningContext
from etlantic.runtime import ActionExecutionHost
from etlantic.runtime.state import RunStatus
from etlantic.secrets import SecretRef, SecretValue


def _context() -> dict[str, Any]:
    return _context_for_token(FOUNDRY_TOKEN)


def _context_for_token(
    token: str, *, run_id: str = "foundry-simulator-test"
) -> dict[str, Any]:
    return {
        "secret": SecretValue(
            _value=token,
            provider="fixture",
            name="foundry-token",
            key="token",
            version="simulator",
        ),
        "run_id": run_id,
        "node": "foundry-output",
    }


def _source_binding(
    base_url: str,
    *,
    dataset_rid: str = FOUNDRY_DATASET,
    branch_name: str = "main",
    transaction_rid: str = PINNED_TRANSACTION,
    **options: Any,
) -> dict[str, Any]:
    return {
        "provider": "foundry",
        "format": "csv",
        "config": {
            "base_url": base_url,
            "dataset_rid": dataset_rid,
            "branch_name": branch_name,
            "transaction_rid": transaction_rid,
            **options,
        },
    }


def _sink_binding(
    base_url: str,
    mode: str,
    *,
    dataset_rid: str = FOUNDRY_DATASET,
    branch_name: str = "main",
    **options: Any,
) -> dict[str, Any]:
    return {
        "provider": "foundry",
        "format": "csv",
        "config": {
            "base_url": base_url,
            "dataset_rid": dataset_rid,
            "branch_name": branch_name,
            "mode": mode,
            **options,
        },
    }


class _OverlapRow(Data):
    id: int
    value: str


class _FoundryOverlapPipeline(Pipeline):
    source: Extract[_OverlapRow] = Extract(asset="foundry-source")
    sink: Load[_OverlapRow] = Load(input=source, asset="foundry-sink")


@pytest.fixture
def foundry_simulator() -> Any:
    simulator = FoundrySimulator()
    with simulator.serve():
        yield simulator


def test_semblance_foundry_api_validates_file_list_and_auth(
    foundry_simulator: Any,
) -> None:
    response = httpx2.get(
        f"{foundry_simulator.base_url}/api/v2/datasets/{FOUNDRY_DATASET}/files",
        params={"branchName": "main"},
        headers={"Authorization": f"Bearer {FOUNDRY_TOKEN}"},
        timeout=5,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["data"] == [
        {
            "path": "folder/a.csv",
            "sizeBytes": "17",
            "transactionRid": PINNED_TRANSACTION,
        }
    ]
    assert body["nextPageToken"] == "page-2"

    unauthorized = httpx2.get(
        f"{foundry_simulator.base_url}/api/v2/datasets/{FOUNDRY_DATASET}/files",
        timeout=5,
    )
    assert unauthorized.status_code == 401
    assert "Bearer" not in unauthorized.text


def test_foundry_action_handlers_run_in_isolated_worker_against_semblance(
    foundry_simulator: Any,
) -> None:
    original = foundry_simulator.files[("main", "folder/a.csv")]
    foundry_simulator.files[("main", "folder/a.csv")] = type(original)(
        b"id,value,api_token\n1,alpha,private-preview-value\n3,gamma,other-secret\n",
        original.branch_name,
        original.transaction_rid,
    )
    ctx = ControlPlaneContext(
        principal=Principal("foundry-action-owner"),
        tenant=TenantRef("foundry-action-tenant"),
        workspace=WorkspaceRef("foundry-action-tenant", "foundry-action-workspace"),
        environment=EnvironmentRef("test"),
        security_domain=SecurityDomain("foundry-action-domain"),
    )
    authorizer = MemoryAuthorizer()
    for action in (
        "connector.test",
        "connector.schema.inspect",
        "connector.preflight",
        "connector.preview",
    ):
        authorizer.grant(ctx, action)

    resolver_calls: list[tuple[str, str]] = []

    def resolve_connection(
        action_ctx: ControlPlaneContext, connection_id: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        assert action_ctx.principal.subject == "foundry-action-owner"
        assert action_ctx.tenant.tenant_id == "foundry-action-tenant"
        resolver_calls.append((action_ctx.principal.subject, connection_id))
        return (
            {
                "provider": "foundry",
                "format": "csv",
                "config": {
                    "base_url": foundry_simulator.base_url,
                    "dataset_rid": FOUNDRY_DATASET,
                    "branch_name": "main",
                    "path_prefix": "folder",
                },
            },
            _context(),
        )

    preflight_calls: list[tuple[str, str, str]] = []
    preview_calls: list[tuple[str, str, str]] = []

    def preflight(
        action_ctx: ControlPlaneContext,
        definition_id: str,
        revision_selector: str,
    ) -> dict[str, Any]:
        preflight_calls.append(
            (action_ctx.principal.subject, definition_id, revision_selector)
        )
        return {"ok": True, "revision_selector": revision_selector}

    def resolve_preview_resource(
        action_ctx: ControlPlaneContext,
        connection_id: str,
        resource_id: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        assert action_ctx.principal.subject == "foundry-action-owner"
        preview_calls.append((action_ctx.principal.subject, connection_id, resource_id))
        return (
            _source_binding(
                foundry_simulator.base_url,
                path_prefix="folder/a.csv",
            ),
            _context(),
        )

    handlers = create_action_handlers(
        resolve_connection,
        preflight=preflight,
        resolve_preview_resource=resolve_preview_resource,
    )
    store = MemoryDurableWorkStore()
    requests = (
        (
            "connector.test",
            {"provider": "foundry", "connection_id": "saved-foundry"},
        ),
        (
            "connector.schema.inspect",
            {
                "provider": "foundry",
                "connection_id": "saved-foundry",
                "max_fields": 1,
            },
        ),
        (
            "connector.preflight",
            {"definition_id": "definition-56", "revision_selector": "rev-7"},
        ),
        (
            "connector.preview",
            {
                "provider": "foundry",
                "connection_id": "saved-foundry",
                "resource_id": "orders-file",
                "max_rows": 1,
                "max_bytes": 4096,
                "redact_fields": ["value"],
            },
        ),
    )
    accepted = [
        store.accept_action_job(
            ctx,
            action=action,
            idempotency_key=f"semblance-action-{index}",
            request=request,
            deadline_at=(datetime.now(UTC) + timedelta(minutes=1)).isoformat(),
        )
        for index, (action, request) in enumerate(requests)
    ]

    worker = ActionExecutionHost(
        store,
        handlers=handlers,
        authorizer=authorizer,
        worker_id="foundry-action-worker",
    )
    assert worker.tick(ctx, limit=4) == 4
    receipts = [store.get_action_job(ctx, job.action_id).to_dict() for job in accepted]
    assert [receipt["status"] for receipt in receipts] == [
        "succeeded",
        "succeeded",
        "succeeded",
        "succeeded",
    ]
    assert receipts[0]["result"] == {"ok": True, "provider": "foundry"}
    schema = receipts[1]["result"]
    assert schema["provider"] == "foundry"
    assert [field["name"] for field in schema["fields"]] == ["id"]
    assert schema["metadata"] == {"inspection": "read_only"}
    assert receipts[2]["result"] == {"ok": True, "revision_selector": "rev-7"}
    preview = receipts[3]["result"]
    assert [column["name"] for column in preview["columns"]] == [
        "id",
        "value",
        "api_token",
    ]
    assert preview["rows"] == [{"id": "1", "value": "***", "api_token": "***"}]
    assert preview["truncated"] is True
    assert resolver_calls == [
        ("foundry-action-owner", "saved-foundry"),
        ("foundry-action-owner", "saved-foundry"),
    ]
    assert preflight_calls == [("foundry-action-owner", "definition-56", "rev-7")]
    assert preview_calls == [("foundry-action-owner", "saved-foundry", "orders-file")]
    encoded_receipts = json.dumps(receipts, sort_keys=True)
    assert FOUNDRY_TOKEN not in encoded_receipts
    assert "private-preview-value" not in encoded_receipts
    assert foundry_simulator.downloaded_paths == [
        "folder/a.csv",
        "folder/a.csv",
        "folder/a.csv",
    ]
    assert foundry_simulator.created_transaction_types == []
    assert foundry_simulator.uploaded_files == []


def test_foundry_preview_rejects_oversized_file_before_downloading(
    foundry_simulator: Any,
) -> None:
    original = foundry_simulator.files[("main", "folder/a.csv")]
    foundry_simulator.files[("main", "folder/a.csv")] = type(original)(
        b"id,value\n" + b"x" * 300,
        original.branch_name,
        original.transaction_rid,
    )

    async def preview() -> dict[str, Any]:
        return await FoundrySourceConnector().preview(
            binding=_source_binding(
                foundry_simulator.base_url,
                path_prefix="folder/a.csv",
            ),
            context=_context(),
            max_rows=5,
            max_bytes=256,
        )

    with pytest.raises(ConnectorReadError) as oversized:
        anyio.run(preview)
    assert oversized.value.code == "PMFND032"
    assert foundry_simulator.downloaded_paths == []
    assert foundry_simulator.uploaded_files == []
    assert foundry_simulator.created_transaction_types == []


def test_foundry_preview_bounds_download_when_server_underreports_file_size(
    foundry_simulator: Any,
) -> None:
    original = foundry_simulator.files[("main", "folder/a.csv")]
    foundry_simulator.files[("main", "folder/a.csv")] = type(original)(
        b"id,value\n" + b"x" * 300,
        original.branch_name,
        original.transaction_rid,
    )
    foundry_simulator.reported_size_overrides["folder/a.csv"] = 1

    async def preview() -> dict[str, Any]:
        return await FoundrySourceConnector().preview(
            binding=_source_binding(
                foundry_simulator.base_url,
                path_prefix="folder/a.csv",
            ),
            context=_context(),
            max_rows=5,
            max_bytes=256,
        )

    with pytest.raises(ConnectorReadError) as oversized:
        anyio.run(preview)
    assert oversized.value.code == "PMFND032"
    assert foundry_simulator.downloaded_paths == ["folder/a.csv"]
    assert foundry_simulator.uploaded_files == []
    assert foundry_simulator.created_transaction_types == []


def test_foundry_source_reads_pinned_paginated_files_over_loopback(
    foundry_simulator: Any,
) -> None:
    connector = FoundrySourceConnector()
    binding = _source_binding(
        foundry_simulator.base_url, path_prefix="folder", batch_size=1
    )
    context = _context()

    async def run() -> tuple[list[dict[str, Any]], list[Any]]:
        plan = await connector.plan_read(binding=binding, context=context)
        batches = [
            batch
            async for batch in connector.read_batches(
                plan=plan, binding=binding, context=context
            )
        ]
        return [dict(row) for batch in batches for row in batch.records], batches

    rows, batches = anyio.run(run)

    assert rows == [
        {"id": "1", "value": "alpha"},
        {"id": "2", "value": "beta"},
    ]
    assert [batch.batch_index for batch in batches] == [0, 1]
    assert batches[-1].exhausted
    assert [query["pageToken"] for query in foundry_simulator.list_queries[-2:]] == [
        None,
        "page-2",
    ]
    assert all(
        query["endTransactionRid"] == PINNED_TRANSACTION
        for query in foundry_simulator.list_queries[-2:]
    )
    assert foundry_simulator.downloaded_paths == ["folder/a.csv", "folder/b.csv"]


@pytest.mark.parametrize(
    ("mode", "transaction_type"),
    [("append", "APPEND"), ("replace", "UPDATE"), ("snapshot", "SNAPSHOT")],
)
def test_foundry_sink_modes_use_simulated_transactions_over_loopback(
    foundry_simulator: Any, mode: str, transaction_type: str
) -> None:
    connector = FoundrySinkConnector()
    binding = _sink_binding(
        foundry_simulator.base_url,
        mode,
        file_path="orders/current.csv" if mode == "replace" else None,
    )
    context = _context()

    async def run() -> CommitReceipt:
        return await write_via_sink_connector(
            connector,
            binding=binding,
            data=[{"id": "1", "value": "alpha"}],
            context=context,
        )

    receipt = anyio.run(run)

    assert receipt.status == "committed"
    assert foundry_simulator.created_transaction_types == [transaction_type]
    file_path = receipt.metadata["file_path"]
    assert foundry_simulator.uploaded_files == [(file_path, b"id,value\n1,alpha\n")]
    assert foundry_simulator.last_upload_branch == "main"
    assert foundry_simulator.transactions[receipt.publication_id or ""] == "COMMITTED"
    listing = httpx2.get(
        f"{foundry_simulator.base_url}/api/v2/datasets/{FOUNDRY_DATASET}/files",
        params={"branchName": "main", "pathPrefix": file_path},
        headers={"Authorization": f"Bearer {FOUNDRY_TOKEN}"},
        timeout=5,
    )
    assert [item["path"] for item in listing.json()["data"]] == [file_path]


def test_lost_commit_ack_reconciles_against_simulated_foundry_state(
    foundry_simulator: Any,
) -> None:
    foundry_simulator.drop_commit_ack = True
    context = _context()
    connector = FoundrySinkConnector()

    async def write() -> CommitReceipt:
        return await write_via_sink_connector(
            connector,
            binding=_sink_binding(foundry_simulator.base_url, "append"),
            data=[{"id": "1", "value": "alpha"}],
            context=context,
        )

    receipt = anyio.run(write)
    assert receipt.status == "unknown"
    recovered = anyio.run(
        lambda: FoundrySinkConnector().reconcile(receipt, context=context)
    )
    assert recovered.status == "committed"
    assert recovered.publication_id == receipt.metadata["transaction_rid"]


def test_lost_transaction_create_ack_stays_unknown_in_simulator(
    foundry_simulator: Any,
) -> None:
    foundry_simulator.drop_create_ack = True
    context = _context()

    async def write() -> CommitReceipt:
        return await write_via_sink_connector(
            FoundrySinkConnector(),
            binding=_sink_binding(
                foundry_simulator.base_url, "append", timeout_seconds=1
            ),
            data=[{"id": "1", "value": "alpha"}],
            context=context,
        )

    receipt = anyio.run(write)
    assert receipt.status == "unknown"
    assert FOUNDRY_TOKEN not in repr(receipt.to_dict())
    reconciled = anyio.run(
        lambda: FoundrySinkConnector().reconcile(receipt, context=context)
    )
    assert reconciled.status == "unknown"
    assert "OPEN" in foundry_simulator.transactions.values()


def test_foundry_sink_aborts_simulated_open_transaction(foundry_simulator: Any) -> None:
    connector = FoundrySinkConnector()
    binding = _sink_binding(foundry_simulator.base_url, "append")
    context = _context()

    async def run() -> CommitReceipt:
        plan = await connector.plan_write(binding=binding, context=context)
        session = await connector.begin_write(
            plan=plan, binding=binding, context=context
        )
        return await connector.abort(session, context=context)

    receipt = anyio.run(run)

    assert receipt.status == "rolled_back"
    assert (
        foundry_simulator.transactions[receipt.metadata["transaction_rid"]] == "ABORTED"
    )
    assert foundry_simulator.uploaded_files == []


def test_foundry_storage_inspection_is_read_only_in_simulator(
    foundry_simulator: Any,
) -> None:
    storage = FoundryStorageConnector()
    binding = {
        "provider": "foundry",
        "format": "csv",
        "config": {
            "base_url": foundry_simulator.base_url,
            "dataset_rid": FOUNDRY_DATASET,
            "branch_name": "main",
            "path_prefix": "orders.csv",
        },
    }

    inspection = anyio.run(
        lambda: storage.inspect_schema(binding=binding, context=_context())
    )

    assert [field["name"] for field in inspection.fields] == ["id", "value"]
    assert foundry_simulator.downloaded_paths == ["orders.csv"]
    assert foundry_simulator.created_transaction_types == []
    assert foundry_simulator.uploaded_files == []


def test_foundry_connector_rejects_non_loopback_http() -> None:
    connector = FoundrySourceConnector()
    binding = _source_binding("http://foundry.example")

    with pytest.raises(ConnectorConfigError, match="HTTPS origin"):
        anyio.run(lambda: connector.plan_read(binding=binding, context=_context()))


def test_independent_semblance_scopes_isolate_dataset_token_branch_and_files() -> None:
    from contextlib import ExitStack

    dataset_a = "ri.foundry.main.dataset.scope-a"
    dataset_b = "ri.foundry.main.dataset.scope-b"
    token_a = "foundry-scope-a-token"
    token_b = "foundry-scope-b-token"
    transaction_a = "ri.foundry.main.transaction.scope-a-pinned"
    transaction_b = "ri.foundry.main.transaction.scope-b-pinned"
    scope_a = FoundrySimulator(
        token=token_a,
        dataset_rid=dataset_a,
        pinned_transaction=transaction_a,
        namespace="scope-a",
        seed_files={"folder/input.csv": b"id,value\n1,scope-a\n"},
    )
    scope_b = FoundrySimulator(
        token=token_b,
        dataset_rid=dataset_b,
        pinned_transaction=transaction_b,
        namespace="scope-b",
        seed_files={"folder/input.csv": b"id,value\n2,scope-b\n"},
    )

    with ExitStack() as stack:
        url_a = stack.enter_context(scope_a.serve())
        url_b = stack.enter_context(scope_b.serve())

        async def read_scope(
            url: str, dataset: str, transaction: str, token: str
        ) -> list[dict[str, str]]:
            connector = FoundrySourceConnector()
            binding = _source_binding(
                url,
                dataset_rid=dataset,
                transaction_rid=transaction,
                path_prefix="folder/",
            )
            context = _context_for_token(token)
            plan = await connector.plan_read(binding=binding, context=context)
            batches = [
                batch
                async for batch in connector.read_batches(
                    plan=plan, binding=binding, context=context
                )
            ]
            return [dict(row) for batch in batches for row in batch.records]

        assert anyio.run(read_scope, url_a, dataset_a, transaction_a, token_a) == [
            {"id": "1", "value": "scope-a"}
        ]
        assert anyio.run(read_scope, url_b, dataset_b, transaction_b, token_b) == [
            {"id": "2", "value": "scope-b"}
        ]
        assert scope_a.list_queries
        assert all(query["datasetRid"] == dataset_a for query in scope_a.list_queries)
        assert scope_b.list_queries
        assert all(query["datasetRid"] == dataset_b for query in scope_b.list_queries)

        async def resolve_overlap_identities() -> tuple[tuple[str, ...], ...]:
            context_a = _context_for_token(token_a)
            source_ids = await FoundrySourceConnector().resource_identities(
                binding=_source_binding(
                    url_a,
                    dataset_rid=dataset_a,
                    transaction_rid=transaction_a,
                    path_prefix="folder/input.csv",
                ),
                context=context_a,
            )
            same_file_ids = await FoundrySinkConnector().resource_identities(
                binding=_sink_binding(
                    url_a,
                    "replace",
                    dataset_rid=dataset_a,
                    branch_name="main",
                    file_path="folder/input.csv",
                ),
                context=context_a,
            )
            other_branch_ids = await FoundrySinkConnector().resource_identities(
                binding=_sink_binding(
                    url_a,
                    "replace",
                    dataset_rid=dataset_a,
                    branch_name="qualification",
                    file_path="folder/input.csv",
                ),
                context=context_a,
            )
            other_dataset_ids = await FoundrySinkConnector().resource_identities(
                binding=_sink_binding(
                    url_a,
                    "replace",
                    dataset_rid=dataset_b,
                    branch_name="main",
                    file_path="folder/input.csv",
                ),
                context=context_a,
            )
            return source_ids, same_file_ids, other_branch_ids, other_dataset_ids

        source_ids, same_file_ids, other_branch_ids, other_dataset_ids = anyio.run(
            resolve_overlap_identities
        )
        assert set(source_ids).intersection(same_file_ids)
        assert not set(source_ids).intersection(other_branch_ids)
        assert not set(source_ids).intersection(other_dataset_ids)
        assert token_a not in repr(source_ids + same_file_ids)

        async def write_branch() -> CommitReceipt:
            connector = FoundrySinkConnector()
            binding = _sink_binding(
                url_a,
                "replace",
                dataset_rid=dataset_a,
                branch_name="qualification",
                file_path="branch/output.csv",
            )
            return await write_via_sink_connector(
                connector,
                binding=binding,
                data=[{"id": "3", "value": "branch-a"}],
                context=_context_for_token(token_a),
            )

        receipt = anyio.run(write_branch)
        committed_transaction = str(receipt.metadata["transaction_rid"])
        assert receipt.status == "committed"
        assert committed_transaction.startswith("ri.foundry.main.transaction.scope-a-")

        async def exercise_scope_modes(
            simulator: FoundrySimulator,
            url: str,
            dataset: str,
            token: str,
            namespace: str,
        ) -> dict[str, str]:
            outcomes: dict[str, str] = {}
            for mode in ("append", "replace", "snapshot"):
                if mode == "append":
                    simulator.drop_commit_ack = True
                binding_options: dict[str, Any] = {
                    "dataset_rid": dataset,
                    "branch_name": "qualification",
                }
                if mode == "replace":
                    binding_options["file_path"] = f"modes/{namespace}/replace.csv"
                else:
                    binding_options["path_prefix"] = f"modes/{namespace}/{mode}"
                context = _context_for_token(
                    token, run_id=f"{namespace}-{mode}-qualification"
                )
                connector = FoundrySinkConnector()
                mode_receipt = await write_via_sink_connector(
                    connector,
                    binding=_sink_binding(url, mode, **binding_options),
                    data=[{"id": "9", "value": f"{namespace}-{mode}"}],
                    context=context,
                )
                if mode == "append":
                    assert mode_receipt.status == "unknown"
                    recovered_mode_receipt = await connector.reconcile(
                        mode_receipt, context=context
                    )
                    assert recovered_mode_receipt.status == "committed"
                    outcomes[mode] = recovered_mode_receipt.status
                else:
                    assert mode_receipt.status == "committed"
                    outcomes[mode] = mode_receipt.status
            return outcomes

        mode_outcomes_a = anyio.run(
            exercise_scope_modes, scope_a, url_a, dataset_a, token_a, "scope-a"
        )
        mode_outcomes_b = anyio.run(
            exercise_scope_modes, scope_b, url_b, dataset_b, token_b, "scope-b"
        )
        assert mode_outcomes_a == {
            "append": "committed",
            "replace": "committed",
            "snapshot": "committed",
        }
        assert mode_outcomes_b == mode_outcomes_a

        headers_a = {"Authorization": f"Bearer {token_a}"}
        branch_listing = httpx2.get(
            f"{url_a}/api/v2/datasets/{dataset_a}/files",
            params={"branchName": "qualification", "pathPrefix": "branch/"},
            headers=headers_a,
            timeout=5,
        )
        main_listing = httpx2.get(
            f"{url_a}/api/v2/datasets/{dataset_a}/files",
            params={"branchName": "main", "pathPrefix": "branch/"},
            headers=headers_a,
            timeout=5,
        )
        other_scope_listing = httpx2.get(
            f"{url_b}/api/v2/datasets/{dataset_b}/files",
            params={"branchName": "main", "pathPrefix": "branch/"},
            headers={"Authorization": f"Bearer {token_b}"},
            timeout=5,
        )
        assert [item["path"] for item in branch_listing.json()["data"]] == [
            "branch/output.csv"
        ]
        assert main_listing.json()["data"] == []
        assert other_scope_listing.json()["data"] == []

        async def read_branch() -> list[dict[str, str]]:
            connector = FoundrySourceConnector()
            binding = _source_binding(
                url_a,
                dataset_rid=dataset_a,
                branch_name="qualification",
                transaction_rid=committed_transaction,
                path_prefix="branch/",
            )
            context = _context_for_token(token_a)
            plan = await connector.plan_read(binding=binding, context=context)
            batches = [
                batch
                async for batch in connector.read_batches(
                    plan=plan, binding=binding, context=context
                )
            ]
            return [dict(row) for batch in batches for row in batch.records]

        assert anyio.run(read_branch) == [{"id": "3", "value": "branch-a"}]
        # Pinned transaction reads identify the branch's committed snapshot;
        # the source connector therefore sends endTransactionRid instead of a
        # branchName on the binary read.
        assert scope_a.last_download_branch == ""

        wrong_dataset = httpx2.get(
            f"{url_a}/api/v2/datasets/{dataset_b}/files",
            headers=headers_a,
            timeout=5,
        )
        wrong_token = httpx2.get(
            f"{url_a}/api/v2/datasets/{dataset_a}/files",
            headers={"Authorization": f"Bearer {token_b}"},
            timeout=5,
        )
        assert wrong_dataset.status_code == 404
        assert wrong_token.status_code == 401
        assert token_a not in wrong_token.text
        assert token_b not in wrong_token.text


def test_managed_foundry_overlap_is_rejected_before_opening_sink_transaction(
    foundry_simulator: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    def reject_overlap(
        simulator: FoundrySimulator,
        *,
        base_url: str,
        dataset_rid: str,
        transaction_rid: str,
        token: str,
    ) -> Any:
        monkeypatch.setenv("ETLANTIC_FOUNDRY_SIMULATOR_TOKEN", token)
        profile = Profile(name="dev", security_mode="development")
        planning = PlanningContext.create(profile=profile)
        secret_ref = SecretRef(
            provider="env", name="ETLANTIC_FOUNDRY_SIMULATOR_TOKEN", key="value"
        )
        planning.registry.register_binding(
            BindingDescriptor(
                binding="foundry-source",
                provider="foundry",
                kind="source",
                format="csv",
                secret_ref=secret_ref,
                config={
                    "base_url": base_url,
                    "dataset_rid": dataset_rid,
                    "branch_name": "main",
                    "transaction_rid": transaction_rid,
                    "path_prefix": "folder/a.csv",
                },
            )
        )
        planning.registry.register_binding(
            BindingDescriptor(
                binding="foundry-sink",
                provider="foundry",
                kind="sink",
                format="csv",
                secret_ref=secret_ref,
                config={
                    "base_url": base_url,
                    "dataset_rid": dataset_rid,
                    "branch_name": "main",
                    "mode": "replace",
                    "file_path": "folder/a.csv",
                },
            )
        )
        runtime = PipelineRuntime()
        runtime.register_source_connector("foundry", FoundrySourceConnector())
        runtime.register_sink_connector("foundry", FoundrySinkConnector())
        return _FoundryOverlapPipeline.run(
            profile=profile, runtime=runtime, context=planning
        )

    report_a = reject_overlap(
        foundry_simulator,
        base_url=foundry_simulator.base_url,
        dataset_rid=FOUNDRY_DATASET,
        transaction_rid=PINNED_TRANSACTION,
        token=FOUNDRY_TOKEN,
    )
    token_b = "foundry-managed-overlap-scope-b-token"
    dataset_b = "ri.foundry.main.dataset.managed-scope-b"
    transaction_b = "ri.foundry.main.transaction.managed-scope-b-pinned"
    simulator_b = FoundrySimulator(
        token=token_b,
        dataset_rid=dataset_b,
        pinned_transaction=transaction_b,
        namespace="managed-scope-b",
        seed_files={"folder/a.csv": b"id,value\n2,scope-b\n"},
    )
    with simulator_b.serve() as url_b:
        report_b = reject_overlap(
            simulator_b,
            base_url=url_b,
            dataset_rid=dataset_b,
            transaction_rid=transaction_b,
            token=token_b,
        )

    for simulator, report, token in (
        (foundry_simulator, report_a, FOUNDRY_TOKEN),
        (simulator_b, report_b, token_b),
    ):
        assert report.status is RunStatus.PARTIAL
        assert any(item.code == "PMEXEC435" for item in report.diagnostics)
        assert simulator.created_transaction_types == []
        assert simulator.uploaded_files == []
        assert token not in report.to_json()
