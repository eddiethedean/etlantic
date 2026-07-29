"""Medallion-oriented plan explain output."""

from __future__ import annotations

from typing import Any

from etlantic.authoring.definition import PipelineDefinition
from etlantic.plan.explain import explain_plan
from etlantic.plan.model import PipelinePlan


def _layer_by_node(plan: PipelinePlan, definition: PipelineDefinition | None) -> dict[str, str]:
    if definition is not None:
        ext = dict(definition.extensions or {})
        layer_map = ext.get("plugin:medallantic.layers")
        if isinstance(layer_map, dict):
            return {str(k): str(v) for k, v in layer_map.items()}
    extensions = dict(plan.metadata.get("extensions") or {})
    layer_map = extensions.get("plugin:medallantic.layers") or extensions.get(
        "layer_by_node"
    )
    if isinstance(layer_map, dict):
        return {str(k): str(v) for k, v in layer_map.items()}
    write_intents = dict(plan.intents.get("write_intents") or {})
    layers: dict[str, str] = {}
    for node, intent in write_intents.items():
        if isinstance(intent, dict):
            meta = intent.get("metadata") or {}
            layer = meta.get("layer")
            if layer is not None:
                layers[str(node)] = str(layer)
    return layers


def explain_medallion_plan(
    plan: PipelinePlan,
    *,
    definition: PipelineDefinition | None = None,
) -> dict[str, Any]:
    """Merge core plan explain with medallion layer and lifecycle metadata."""
    base = explain_plan(plan)
    layer_map = _layer_by_node(plan, definition)
    write_intents = dict(plan.intents.get("write_intents") or {})
    incremental = dict(plan.intents.get("incremental_strategies") or {})
    steps = []
    for step in base.get("steps") or []:
        if not isinstance(step, dict):
            steps.append(step)
            continue
        node = str(step.get("node") or "")
        enriched = dict(step)
        if node in layer_map:
            enriched["layer"] = layer_map[node]
        wi = write_intents.get(node)
        if isinstance(wi, dict):
            enriched["write_intent"] = wi
        if node in incremental:
            enriched["incremental_strategy"] = incremental[node]
        steps.append(enriched)
    accept_rates: dict[str, Any] = {}
    if definition is not None:
        plugin_meta = dict((definition.extensions or {}).get("plugin:medallantic") or {})
        accept_rates = dict(plugin_meta.get("accept_rates") or {})
    elif isinstance(plan.metadata.get("plugin:medallantic"), dict):
        accept_rates = dict(plan.metadata["plugin:medallantic"].get("accept_rates") or {})
    return {
        **base,
        "schema": "medallantic.explain/1",
        "layers": layer_map,
        "steps": steps,
        "accept_rates": accept_rates,
        "write_intents": write_intents,
        "incremental_strategies": incremental,
    }
