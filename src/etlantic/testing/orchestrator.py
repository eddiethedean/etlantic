"""Orchestrator plugin conformance helpers."""

from __future__ import annotations

from typing import Any

from etlantic.orchestration.protocol import (
    ORCHESTRATION_PROTOCOL_VERSION,
    CompilationContext,
    OrchestratorPlugin,
)
from etlantic.plan.model import PipelinePlan
from etlantic.runtime.logging import redact_message


def assert_orchestrator_plugin_info(plugin: OrchestratorPlugin, *, engine: str) -> None:
    info = plugin.info
    assert info.engine == engine
    assert info.protocol_version == ORCHESTRATION_PROTOCOL_VERSION
    assert info.capabilities is not None
    assert info.capabilities.supports("orchestration") or bool(
        getattr(info.capabilities, "orchestration", False)
    )


def run_orchestrator_conformance_suite(
    plugin: OrchestratorPlugin,
    *,
    engine: str,
    plan: PipelinePlan,
    context: CompilationContext | None = None,
) -> Any:
    """Compile a plan and assert a secret-free artifact is produced."""
    assert_orchestrator_plugin_info(plugin, engine=engine)
    ctx = context or CompilationContext(target=engine)
    artifact = plugin.compile(plan, context=ctx)
    assert artifact is not None
    assert artifact.target == engine or artifact.target == plugin.info.engine
    source = artifact.source or ""
    assert source == redact_message(source), (
        "Compiled artifact source contains secret-like text"
    )
    meta = str(artifact.metadata or {})
    assert meta == redact_message(meta), (
        "Compiled artifact metadata contains secret-like text"
    )
    explain = artifact.explain()
    assert "dag_id" in explain
    return artifact
