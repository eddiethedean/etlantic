from __future__ import annotations

import hashlib
import json
from typing import Any
from urllib.parse import unquote

import anyio
import httpx
import pytest
from etlantic_foundry.connectors import (
    FoundrySinkConnector,
    FoundrySourceConnector,
    FoundryStorageConnector,
)

from etlantic.connectors.errors import ConnectorConfigError, ConnectorWriteError
from etlantic.connectors.models import CommitReceipt
from etlantic.connectors.session import write_via_sink_connector
from etlantic.secrets import SecretValue

BASE = "https://foundry.example"
DATASET = "ri.foundry.main.dataset.test"
TRANSACTION = "ri.foundry.main.transaction.pinned"
TOKEN = "foundry-test-token-do-not-log"


def _secret() -> dict[str, Any]:
    return {
        "secret": SecretValue(
            _value=TOKEN,
            provider="fixture",
            name="foundry-token",
            key="token",
            version="test",
        ),
        "run_id": "foundry-run-1",
        "node": "foundry-output",
    }


def _source_binding(**options: Any) -> dict[str, Any]:
    return {
        "provider": "foundry",
        "format": "csv",
        "config": {
            "base_url": BASE,
            "dataset_rid": DATASET,
            "branch_name": "main",
            "transaction_rid": TRANSACTION,
            **options,
        },
    }


def _sink_binding(mode: str = "append", **options: Any) -> dict[str, Any]:
    return {
        "provider": "foundry",
        "format": "csv",
        "config": {
            "base_url": BASE,
            "dataset_rid": DATASET,
            "branch_name": "main",
            "mode": mode,
            **options,
        },
    }


def test_source_reads_pinned_paginated_csv_and_records_identity() -> None:
    requests: list[httpx.Request] = []
    contents = {
        "folder/a.csv": b"id,value\n1,alpha\n",
        "folder/b.csv": b"id,value\n2,beta\n",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["Authorization"] == f"Bearer {TOKEN}"
        if request.url.path.endswith(f"/transactions/{TRANSACTION}"):
            return httpx.Response(200, json={"rid": TRANSACTION, "status": "COMMITTED"})
        if request.url.path.endswith("/files"):
            if request.url.params.get("pageToken"):
                return httpx.Response(
                    200,
                    json={
                        "data": [{"path": "folder/b.csv", "sizeBytes": "16"}],
                    },
                )
            return httpx.Response(
                200,
                json={
                    "data": [{"path": "folder/a.csv", "sizeBytes": "17"}],
                    "nextPageToken": "next-page",
                },
            )
        if request.url.path.endswith("/content"):
            path = unquote(
                request.url.path.split("/files/", 1)[1].removesuffix("/content")
            )
            return httpx.Response(200, content=contents[path])
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    connector = FoundrySourceConnector(transport=httpx.MockTransport(handler))
    binding = _source_binding(path_prefix="folder", batch_size=1)
    context = _secret()

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
    assert rows == [{"id": "1", "value": "alpha"}, {"id": "2", "value": "beta"}]
    assert [batch.batch_index for batch in batches] == [0, 1]
    assert batches[-1].exhausted
    assert len(batches[0].identities) == 2
    assert (
        batches[0].identities[0].content_sha256
        == hashlib.sha256(contents["folder/a.csv"]).hexdigest()
    )
    listing_requests = [
        request for request in requests if request.url.path.endswith("/files")
    ]
    assert len(listing_requests) == 2
    assert all(
        request.url.params.get("endTransactionRid") == TRANSACTION
        for request in listing_requests
    )
    assert all(
        request.url.params.get("branchName") is None for request in listing_requests
    )
    assert "Bearer" not in repr(batches)


@pytest.mark.parametrize(
    ("mode", "transaction_type"),
    [("append", "APPEND"), ("replace", "UPDATE"), ("snapshot", "SNAPSHOT")],
)
def test_sink_modes_use_open_foundry_transactions(
    mode: str, transaction_type: str
) -> None:
    events: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == f"Bearer {TOKEN}"
        path = request.url.path
        if path.endswith("/transactions"):
            events.append(("create", json.loads(request.content)["transactionType"]))
            return httpx.Response(
                200,
                json={"rid": f"ri.foundry.main.transaction.{mode}", "status": "OPEN"},
            )
        if path.endswith("/files"):
            return httpx.Response(200, json={"data": []})
        if path.endswith("/upload"):
            events.append(("upload", request.content.decode("utf-8")))
            return httpx.Response(
                200,
                json={
                    "path": unquote(path.split("/files/", 1)[1].removesuffix("/upload"))
                },
            )
        if path.endswith("/commit"):
            events.append(("commit", ""))
            return httpx.Response(200, json={"status": "COMMITTED"})
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    connector = FoundrySinkConnector(transport=httpx.MockTransport(handler))
    binding = _sink_binding(
        mode, file_path="orders/current.csv" if mode == "replace" else None
    )
    context = _secret()

    async def run() -> CommitReceipt:
        return await write_via_sink_connector(
            connector,
            binding=binding,
            data=[{"id": "1", "value": "alpha"}],
            context=context,
        )

    receipt = anyio.run(run)
    assert receipt.status == "committed"
    assert events[0] == ("create", transaction_type)
    assert events[1][0] == "upload"
    assert events[2] == ("commit", "")
    assert events[1][1] == "id,value\n1,alpha\n"
    if mode == "replace":
        assert receipt.metadata["file_path"] == "orders/current.csv"
    else:
        assert receipt.metadata["file_path"].startswith("etlantic/effects/")


def test_sink_enforces_byte_bound_during_staging_without_poisoning_session() -> None:
    uploaded: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/transactions"):
            return httpx.Response(
                200,
                json={"rid": "ri.foundry.main.transaction.bounded", "status": "OPEN"},
            )
        if path.endswith("/files"):
            return httpx.Response(200, json={"data": []})
        if path.endswith("/upload"):
            uploaded.append(request.content)
            return httpx.Response(
                200,
                json={
                    "path": unquote(path.split("/files/", 1)[1].removesuffix("/upload"))
                },
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    connector = FoundrySinkConnector(transport=httpx.MockTransport(handler))
    binding = _sink_binding("append", format="json", max_bytes=15)
    binding["format"] = "json"
    context = _secret()

    async def run() -> None:
        plan = await connector.plan_write(binding=binding, context=context)
        session = await connector.begin_write(
            plan=plan, binding=binding, context=context
        )
        with pytest.raises(ConnectorWriteError, match="max_bytes"):
            await connector.write_batch(
                session, [{"value": "0123456789"}], context=context
            )
        await connector.write_batch(session, [{"value": "x"}], context=context)
        await connector.prepare(session, context=context)

    anyio.run(run)

    assert uploaded == [b'[{"value":"x"}]']


def test_lost_commit_ack_reconciles_after_connector_restart() -> None:
    committed = False
    transaction_rid = "ri.foundry.main.transaction.lost-ack"
    expected_payload = b"id,value\n1,alpha\n"

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal committed
        path = request.url.path
        if path.endswith("/transactions"):
            return httpx.Response(200, json={"rid": transaction_rid, "status": "OPEN"})
        if path.endswith("/files"):
            return httpx.Response(200, json={"data": []})
        if path.endswith("/upload"):
            assert request.content == expected_payload
            uploaded_path = unquote(path.split("/files/", 1)[1].removesuffix("/upload"))
            return httpx.Response(200, json={"path": uploaded_path})
        if path.endswith("/commit"):
            committed = True
            raise httpx.ReadTimeout("simulated lost acknowledgement")
        if path.endswith(f"/transactions/{transaction_rid}"):
            return httpx.Response(
                200,
                json={
                    "rid": transaction_rid,
                    "status": "COMMITTED" if committed else "OPEN",
                },
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    transport = httpx.MockTransport(handler)
    connector = FoundrySinkConnector(transport=transport)
    context = _secret()

    async def write() -> CommitReceipt:
        return await write_via_sink_connector(
            connector,
            binding=_sink_binding("append"),
            data=[{"id": "1", "value": "alpha"}],
            context=context,
        )

    receipt = anyio.run(write)
    assert receipt.status == "unknown"
    assert receipt.metadata.get("dataset_rid") == DATASET, receipt.to_dict()

    async def recover() -> Any:
        return await FoundrySinkConnector(transport=transport).reconcile(
            receipt, context=context
        )

    recovered = anyio.run(recover)
    assert recovered.status == "committed", recovered.message
    assert recovered.publication_id == transaction_rid


def test_lost_transaction_create_ack_is_unknown_and_scoped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/transactions")
        raise httpx.ReadTimeout("simulated transaction create acknowledgement loss")

    connector = FoundrySinkConnector(transport=httpx.MockTransport(handler))
    context = _secret()

    async def write() -> CommitReceipt:
        return await write_via_sink_connector(
            connector,
            binding=_sink_binding("append"),
            data=[{"id": "1", "value": "alpha"}],
            context=context,
        )

    receipt = anyio.run(write)
    assert receipt.status == "unknown"
    assert receipt.session_id is not None
    assert receipt.metadata["dataset_rid"] == DATASET
    assert TOKEN not in repr(receipt.to_dict())
    recovered = anyio.run(
        lambda: FoundrySinkConnector(transport=httpx.MockTransport(handler)).reconcile(
            receipt, context=context
        )
    )
    assert recovered.status == "unknown"


def test_foundry_scopes_distinct_dataset_and_branch_configurations() -> None:
    first = _sink_binding("append")
    second = _sink_binding("append")
    second["config"]["dataset_rid"] = "ri.foundry.main.dataset.other"
    second["config"]["branch_name"] = "qualification"
    connector = FoundrySinkConnector()

    async def plans() -> tuple[Any, Any]:
        return (
            await connector.plan_write(binding=first, context=_secret()),
            await connector.plan_write(binding=second, context=_secret()),
        )

    first_plan, second_plan = anyio.run(plans)
    assert first_plan.metadata["dataset_rid"] != second_plan.metadata["dataset_rid"]
    assert first_plan.metadata["branch_name"] != second_plan.metadata["branch_name"]
    assert first_plan.metadata["file_path"] != second_plan.metadata["file_path"]


def test_foundry_rejects_unpinned_source_and_unsafe_paths() -> None:
    source = FoundrySourceConnector(
        transport=httpx.MockTransport(lambda request: httpx.Response(200))
    )
    unpinned = _source_binding()
    del unpinned["config"]["transaction_rid"]

    async def make_source_plan() -> Any:
        return await source.plan_read(binding=unpinned, context=_secret())

    with pytest.raises(ConnectorConfigError, match="pinned transaction_rid"):
        anyio.run(make_source_plan)

    sink = FoundrySinkConnector(
        transport=httpx.MockTransport(lambda request: httpx.Response(200))
    )

    async def make_sink_plan() -> Any:
        return await sink.plan_write(
            binding=_sink_binding("replace", file_path="../outside.csv"),
            context=_secret(),
        )

    with pytest.raises(ConnectorConfigError, match="unsafe segment"):
        anyio.run(make_sink_plan)


def test_storage_inspection_reads_csv_header_without_mutations() -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.method)
        if request.url.path.endswith("/files"):
            return httpx.Response(
                200,
                json={"data": [{"path": "orders.csv", "sizeBytes": "13"}]},
            )
        if request.url.path.endswith("/content"):
            return httpx.Response(200, content=b"id,value\n1,a\n")
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    storage = FoundryStorageConnector(transport=httpx.MockTransport(handler))
    inspection = anyio.run(
        lambda: storage.inspect_schema(
            binding={
                "provider": "foundry",
                "format": "csv",
                "config": {
                    "base_url": BASE,
                    "dataset_rid": DATASET,
                    "branch_name": "main",
                },
            },
            context=_secret(),
        )
    )
    assert [field["name"] for field in inspection.fields] == ["id", "value"]
    assert requests == ["GET", "GET"]
