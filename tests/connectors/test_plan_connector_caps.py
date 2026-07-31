"""Plan-time connector capability negotiation tests."""

from __future__ import annotations

import pytest

from etlantic.connectors.negotiate import (
    PMCONN850,
    assert_binding_connector_capabilities,
)
from etlantic.exceptions import PipelineValidationError
from etlantic.registry import BindingDescriptor


def test_local_files_unsupported_capability_fails_closed() -> None:
    bindings = {
        "src": BindingDescriptor(
            binding="landing",
            provider="local-files",
            kind="source",
            mode="snapshot",
            required_capabilities=("write.merge",),
            config={"glob": "*.csv", "root": "inbox"},
        )
    }
    with pytest.raises(PipelineValidationError) as exc:
        assert_binding_connector_capabilities(bindings)
    codes = {d.code for d in exc.value.report.diagnostics}
    assert PMCONN850 in codes


def test_local_files_incremental_mode_ok() -> None:
    bindings = {
        "src": BindingDescriptor(
            binding="landing",
            provider="local-files",
            kind="source",
            mode="incremental",
            required_capabilities=("source.incremental_cursor",),
            config={"glob": "*.csv", "checkpoint": "ck"},
        )
    }
    assert_binding_connector_capabilities(bindings)


def test_iceberg_partition_replace_fails_at_plan() -> None:
    bindings = {
        "out": BindingDescriptor(
            binding="lake",
            provider="iceberg",
            kind="sink",
            mode="partition_replace",
            required_capabilities=(),
            config={"identifier": "db.t"},
        )
    }
    with pytest.raises(PipelineValidationError) as exc:
        assert_binding_connector_capabilities(bindings)
    assert any(d.code == PMCONN850 for d in exc.value.report.diagnostics)
