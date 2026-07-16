"""Reusable dataframe plugin conformance helpers."""

from __future__ import annotations

from typing import Any

from pipelantic.capabilities import PluginCapabilities
from pipelantic.dataframe.protocol import (
    DATAFRAME_PROTOCOL_VERSION,
    DataframeExecutionContext,
    DataframePlugin,
    ValidationDecision,
)


def assert_plugin_info(plugin: DataframePlugin, *, engine: str) -> None:
    info = plugin.info
    assert info.engine == engine
    assert info.protocol_version == DATAFRAME_PROTOCOL_VERSION
    assert info.capabilities is not None
    assert info.capabilities.supports("dataframe")
    assert info.capabilities.supports("eager")


def assert_roundtrip_records(
    plugin: DataframePlugin,
    *,
    rows: list[dict[str, Any]],
    contract_type: type[Any] | None = None,
) -> None:
    context = DataframeExecutionContext(
        run_id="conformance",
        pipeline_id="conformance",
        plan_id="plan",
        step_name="step",
        engine=plugin.info.engine,
        collect=True,
    )
    frame = plugin.materialize_input(
        rows, contract_type=contract_type, context=context, port_name="in"
    )
    frame, decision, _ = plugin.validate_frame(
        frame,
        contract_type=contract_type,
        context=context,
        boundary="input_validation",
        port_name="in",
    )
    assert decision in {
        ValidationDecision.PASSED,
        ValidationDecision.SKIPPED,
        ValidationDecision.WARNED,
        ValidationDecision.OBSERVED,
    }
    records = plugin.to_records(frame, contract_type=contract_type)
    assert len(records) == len(rows)


def run_conformance_suite(
    plugin: DataframePlugin,
    *,
    engine: str,
    sample_rows: list[dict[str, Any]],
    contract_type: type[Any] | None = None,
) -> None:
    """Minimal conformance checks for third-party dataframe plugins."""
    assert_plugin_info(plugin, engine=engine)
    caps: PluginCapabilities | None = plugin.info.capabilities
    assert caps is not None
    if engine == "pandas":
        assert caps.supports("lazy") is False
    assert_roundtrip_records(plugin, rows=sample_rows, contract_type=contract_type)
    assert callable(plugin.collect_if_needed)
    assert callable(plugin.ensure_ownership)
    assert callable(plugin.inspect_schema)
