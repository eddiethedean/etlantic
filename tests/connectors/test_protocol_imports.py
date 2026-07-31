"""Protocol and public import smoke tests."""

from __future__ import annotations

import etlantic as etl
from etlantic.connectors import (
    SINK_PROTOCOL,
    SOURCE_PROTOCOL,
    STORAGE_PROTOCOL,
    SinkConnector,
    SourceConnector,
    StorageConnector,
)
from etlantic.connectors.local_files import LocalFilesSourceConnector
from etlantic.connectors.maturity import ConnectorMaturity


def test_lazy_namespace_connectors() -> None:
    mod = etl.connectors
    assert mod.__name__ == "etlantic.connectors"
    assert SOURCE_PROTOCOL == "etlantic.source/1"
    assert SINK_PROTOCOL == "etlantic.sink/1"
    assert STORAGE_PROTOCOL == "etlantic.storage/1"


def test_protocols_are_runtime_checkable() -> None:
    connector = LocalFilesSourceConnector()
    assert isinstance(connector, SourceConnector)
    assert connector.info().protocol == SOURCE_PROTOCOL
    assert connector.info().maturity is ConnectorMaturity.PREVIEW


def test_protocol_method_names() -> None:
    for proto, names in (
        (SourceConnector, ("info", "plan_read", "read_batches", "propose_cursor")),
        (
            SinkConnector,
            (
                "info",
                "plan_write",
                "begin_write",
                "write_batch",
                "prepare",
                "commit",
                "abort",
                "reconcile",
                "cleanup",
            ),
        ),
        (StorageConnector, ("info", "inspect_schema")),
    ):
        for name in names:
            assert hasattr(proto, name), f"{proto.__name__} missing {name}"
