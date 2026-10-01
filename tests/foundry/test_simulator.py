from __future__ import annotations

from typing import Any

import anyio
import httpx
import pytest
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

from etlantic.connectors.errors import ConnectorConfigError
from etlantic.connectors.models import CommitReceipt
from etlantic.connectors.session import write_via_sink_connector
from etlantic.secrets import SecretValue


def _context() -> dict[str, Any]:
    return {
        "secret": SecretValue(
            _value=FOUNDRY_TOKEN,
            provider="fixture",
            name="foundry-token",
            key="token",
            version="simulator",
        ),
        "run_id": "foundry-simulator-test",
        "node": "foundry-output",
    }


def _source_binding(base_url: str, **options: Any) -> dict[str, Any]:
    return {
        "provider": "foundry",
        "format": "csv",
        "config": {
            "base_url": base_url,
            "dataset_rid": FOUNDRY_DATASET,
            "branch_name": "main",
            "transaction_rid": PINNED_TRANSACTION,
            **options,
        },
    }


def _sink_binding(base_url: str, mode: str, **options: Any) -> dict[str, Any]:
    return {
        "provider": "foundry",
        "format": "csv",
        "config": {
            "base_url": base_url,
            "dataset_rid": FOUNDRY_DATASET,
            "branch_name": "main",
            "mode": mode,
            **options,
        },
    }


@pytest.fixture
def foundry_simulator() -> Any:
    simulator = FoundrySimulator()
    with simulator.serve():
        yield simulator


def test_semblance_foundry_api_validates_file_list_and_auth(
    foundry_simulator: Any,
) -> None:
    response = httpx.get(
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

    unauthorized = httpx.get(
        f"{foundry_simulator.base_url}/api/v2/datasets/{FOUNDRY_DATASET}/files",
        timeout=5,
    )
    assert unauthorized.status_code == 401
    assert "Bearer" not in unauthorized.text


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
    listing = httpx.get(
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
