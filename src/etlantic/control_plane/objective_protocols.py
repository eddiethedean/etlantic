"""Delivery objective and notification protocols (CP4)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from etlantic.control_plane.models import ControlPlaneContext
from etlantic.control_plane.objective_models import (
    DeliveryObjective,
    ObjectiveEvaluation,
    ObjectiveNotification,
)


@runtime_checkable
class NotificationProvider(Protocol):
    """Independently installable notification channel."""

    channel: str

    def deliver(
        self,
        ctx: ControlPlaneContext,
        *,
        destination_ref: str,
        subject: str,
        body: Mapping[str, Any],
    ) -> bool:
        """Deliver a redacted notification payload; never include secrets."""


@runtime_checkable
class ObjectiveStore(Protocol):
    """Versioned objectives with durable breach/recovery evaluation."""

    def upsert_objective(
        self, ctx: ControlPlaneContext, *, objective: DeliveryObjective
    ) -> DeliveryObjective: ...

    def get_objective(
        self, ctx: ControlPlaneContext, *, objective_id: str
    ) -> DeliveryObjective: ...

    def evaluate(
        self,
        ctx: ControlPlaneContext,
        *,
        objective_id: str,
        reference_at: datetime,
        now: datetime | None = None,
        submission_id: str | None = None,
        completed: bool = False,
    ) -> ObjectiveEvaluation:
        """Evaluate deadlines; dedupe repeated breach/recovery transitions."""

    def acknowledge(
        self,
        ctx: ControlPlaneContext,
        *,
        evaluation_id: str,
    ) -> ObjectiveEvaluation: ...

    def route_notification(
        self,
        ctx: ControlPlaneContext,
        *,
        evaluation_id: str,
        channel: str,
        destination_ref: str,
        authorized_destinations: Sequence[str],
        provider: NotificationProvider,
    ) -> ObjectiveNotification:
        """Route only to authorized destinations; deny otherwise."""

    def list_evaluations(
        self, ctx: ControlPlaneContext, *, objective_id: str, limit: int = 100
    ) -> Sequence[ObjectiveEvaluation]: ...


__all__ = ["NotificationProvider", "ObjectiveStore"]
