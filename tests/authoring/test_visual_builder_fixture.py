"""Visual-builder public-API fixture (no private ETLantic modules)."""

from __future__ import annotations

from etlantic.authoring import (
    EditCommand,
    apply_edit,
    discover_authoring_catalog,
    negotiate_capabilities,
    pipeline_from_json,
    pipeline_to_json,
    plan_preview,
    structural_validate_preview,
)
from etlantic.authoring import definition_from_pipeline
from examples.memory_customers import CustomerPipeline


def test_visual_builder_public_workflow() -> None:
    negotiation = negotiate_capabilities()
    assert "etlantic.pipeline/1" in negotiation["document_versions"]
    assert "validate" in negotiation["lifecycle_actions"]

    defn = definition_from_pipeline(CustomerPipeline)
    catalog = discover_authoring_catalog(definition=defn)
    kinds = {e.kind for e in catalog.entries}
    assert "contract" in kinds
    assert "transformation" in kinds

    # Autosave / reload
    text = pipeline_to_json(defn)
    reloaded = pipeline_from_json(text)
    assert reloaded.pipeline_id == defn.pipeline_id

    # Edit: disconnect then reconnect
    edge0 = reloaded.edges[0]
    disconnected = apply_edit(
        reloaded,
        EditCommand(
            op="disconnect",
            payload={
                "producer_node": edge0.producer_node,
                "producer_port": edge0.producer_port,
                "consumer_node": edge0.consumer_node,
                "consumer_port": edge0.consumer_port,
            },
        ),
    ).definition
    assert len(disconnected.edges) == len(reloaded.edges) - 1

    restored = apply_edit(
        disconnected,
        EditCommand(
            op="connect",
            payload={
                "producer_node": edge0.producer_node,
                "producer_port": edge0.producer_port,
                "consumer_node": edge0.consumer_node,
                "consumer_port": edge0.consumer_port,
                "producer_contract_id": edge0.producer_contract_id,
                "consumer_contract_id": edge0.consumer_contract_id,
            },
        ),
        expected_token=disconnected.fingerprint,
    ).definition
    assert len(restored.edges) == len(reloaded.edges)

    report = structural_validate_preview(restored, profile="development")
    assert isinstance(report.diagnostics, tuple)
    plan, plan_report = plan_preview(restored, profile="development")
    assert plan_report is not None
    # Plan may succeed when implementations are harvestable from class registry.
    assert plan is not None or plan_report.has_errors
