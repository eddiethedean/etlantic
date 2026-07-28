"""Lifecycle policy composition helpers (domain-neutral; facades supply defaults)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from etlantic.reliability import MaterializationMode, WriteMode
from etlantic.runtime.request import RunIntent


class LifecycleAction(StrEnum):
    """High-level lifecycle action applied to a subject."""

    PRESERVE = "preserve"
    REFRESH = "refresh"
    PUBLISH = "publish"
    VALIDATE = "validate"
    INCREMENT = "increment"
    INITIALIZE = "initialize"


@dataclass(frozen=True, slots=True)
class LifecyclePolicy:
    """Layer-independent lifecycle defaults for a subject.

    Facades (e.g. Medallantic) map bronze/silver/gold onto these policies
    without promoting medallion vocabulary into core wire schemas.
    """

    subject_id: str
    default_action: LifecycleAction
    write_mode: WriteMode = WriteMode.OVERWRITE
    materialization: MaterializationMode = MaterializationMode.EAGER
    incremental_field: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "default_action": self.default_action.value,
            "write_mode": self.write_mode.value,
            "materialization": self.materialization.value,
            "incremental_field": self.incremental_field,
            "metadata": dict(self.metadata),
        }


def resolve_lifecycle_action(
    *,
    intent: RunIntent,
    policy: LifecyclePolicy | None = None,
) -> LifecycleAction:
    """Resolve the effective lifecycle action for a run intent."""
    if intent is RunIntent.VALIDATE:
        return LifecycleAction.VALIDATE
    if intent is RunIntent.INITIALIZE:
        return LifecycleAction.INITIALIZE
    if intent is RunIntent.REFRESH:
        return LifecycleAction.REFRESH
    if intent is RunIntent.INCREMENTAL:
        return LifecycleAction.INCREMENT
    if policy is not None:
        return policy.default_action
    return LifecycleAction.PUBLISH


def write_mode_for_lifecycle(
    action: LifecycleAction,
    *,
    policy: LifecyclePolicy | None = None,
) -> WriteMode:
    """Map a lifecycle action to a portable write mode."""
    if action is LifecycleAction.VALIDATE:
        return WriteMode.NO_WRITE
    if action is LifecycleAction.PRESERVE:
        return WriteMode.APPEND
    if action is LifecycleAction.INCREMENT:
        return WriteMode.APPEND
    if action in {LifecycleAction.REFRESH, LifecycleAction.INITIALIZE}:
        return WriteMode.OVERWRITE
    if policy is not None:
        return policy.write_mode
    return WriteMode.OVERWRITE
