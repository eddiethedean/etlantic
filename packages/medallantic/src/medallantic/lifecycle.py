"""Medallantic layer lifecycle defaults (facade-only; not core wire vocabulary)."""

from __future__ import annotations

from typing import Any

from etlantic.reliability import MaterializationMode, WriteMode
from etlantic.runtime.incremental import IncrementalStrategy
from etlantic.runtime.lifecycle_policy import LifecycleAction, LifecyclePolicy

# Facade mapping: medallion layers → domain-neutral lifecycle policies.
_LAYER_DEFAULTS: dict[str, LifecycleAction] = {
    "bronze": LifecycleAction.PRESERVE,
    "silver": LifecycleAction.REFRESH,
    "gold": LifecycleAction.PUBLISH,
}

_LAYER_WRITE: dict[str, WriteMode] = {
    "bronze": WriteMode.APPEND,
    "silver": WriteMode.OVERWRITE,
    "gold": WriteMode.OVERWRITE,
}

_LAYER_MATERIALIZATION: dict[str, MaterializationMode] = {
    "bronze": MaterializationMode.EAGER,
    "silver": MaterializationMode.EAGER,
    "gold": MaterializationMode.PUBLISH,
}


def lifecycle_policy_for_layer(
    *,
    subject_id: str,
    layer: str,
    incremental_field: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> LifecyclePolicy:
    """Return the default lifecycle policy for a medallion layer."""
    key = (layer or "").strip().lower()
    return LifecyclePolicy(
        subject_id=subject_id,
        default_action=_LAYER_DEFAULTS.get(key, LifecycleAction.PUBLISH),
        write_mode=_LAYER_WRITE.get(key, WriteMode.OVERWRITE),
        materialization=_LAYER_MATERIALIZATION.get(key, MaterializationMode.EAGER),
        incremental_field=incremental_field,
        metadata={
            "medallantic.layer": key,
            **dict(metadata or {}),
        },
    )


def incremental_strategy_for_step(
    *,
    subject_id: str,
    layer: str,
    incremental_column: str | None = None,
    watermark_column: str | None = None,
) -> IncrementalStrategy | None:
    """Map Medallantic incremental/watermark columns onto IncrementalStrategy."""
    field = incremental_column or watermark_column
    if not field:
        return None
    return IncrementalStrategy.watermark(
        subject_id=subject_id,
        field=field,
        metadata={"medallantic.layer": (layer or "").strip().lower()},
    )


def default_write_mode_for_layer(layer: str) -> WriteMode:
    return _LAYER_WRITE.get((layer or "").strip().lower(), WriteMode.OVERWRITE)
