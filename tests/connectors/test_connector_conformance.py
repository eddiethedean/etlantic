"""Connector conformance suite tests."""

from __future__ import annotations

from etlantic.connectors import create_local_files_source
from etlantic.connectors.compatibility import StorageBindingAdapter
from etlantic.storage.memory import MemoryStorage
from etlantic.testing.connectors import (
    SECRET_SENTINEL,
    run_sink_connector_conformance_suite,
    run_source_connector_conformance_suite,
)


def test_source_conformance_local_files() -> None:
    connector = create_local_files_source()
    results = run_source_connector_conformance_suite(connector)
    cases = {r["case"] for r in results}
    assert "source.batch_snapshot" in cases
    assert "source.file_glob" in cases
    assert "format.csv" in cases
    assert "fault.empty_listing_fail" in cases
    assert "fault.invalid_glob" in cases
    assert all(r.get("ok") for r in results)
    assert SECRET_SENTINEL.startswith("ETLANTIC_CONNECTOR_SECRET")


def test_sink_conformance_storage_binding_adapter() -> None:
    adapter = StorageBindingAdapter(MemoryStorage(), provider="memory")
    results = run_sink_connector_conformance_suite(adapter)
    cases = {r["case"] for r in results}
    assert "sink.commit_lifecycle" in cases
    assert "sink.abort" in cases
    assert all(r.get("ok") for r in results)


def test_sink_conformance_default_adapter() -> None:
    results = run_sink_connector_conformance_suite()
    assert any(r["case"] == "sink.commit_lifecycle" for r in results)
