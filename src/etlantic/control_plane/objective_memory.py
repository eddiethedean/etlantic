"""In-memory delivery objectives, evaluation, and notify fakes (CP4)."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any

from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.models import ControlPlaneContext
from etlantic.control_plane.objective_models import (
    DeliveryObjective,
    ObjectiveEvaluation,
    ObjectiveNotification,
)
from etlantic.control_plane.objective_protocols import NotificationProvider


def _scope(ctx: ControlPlaneContext) -> tuple[str, str]:
    return ctx.tenant.tenant_id, ctx.workspace.workspace_id


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class MemoryNotificationProvider:
    channel: str
    delivered: list[dict[str, Any]] = field(default_factory=list)
    fail: bool = False

    def deliver(
        self,
        ctx: ControlPlaneContext,
        *,
        destination_ref: str,
        subject: str,
        body: Mapping[str, Any],
    ) -> bool:
        if self.fail:
            return False
        self.delivered.append(
            {
                "tenant_id": ctx.tenant.tenant_id,
                "workspace_id": ctx.workspace.workspace_id,
                "destination_ref": destination_ref,
                "subject": subject,
                "body": dict(body),
                "channel": self.channel,
            }
        )
        return True


def memory_email_provider() -> MemoryNotificationProvider:
    return MemoryNotificationProvider(channel="email")


def memory_webhook_provider() -> MemoryNotificationProvider:
    return MemoryNotificationProvider(channel="webhook")


def memory_slack_provider() -> MemoryNotificationProvider:
    return MemoryNotificationProvider(channel="slack")


def memory_incident_provider() -> MemoryNotificationProvider:
    return MemoryNotificationProvider(channel="incident")


class MemoryObjectiveStore:
    def __init__(self) -> None:
        self._objectives: dict[tuple[str, str, str], DeliveryObjective] = {}
        self._evaluations: dict[tuple[str, str, str], ObjectiveEvaluation] = {}
        self._by_objective: dict[tuple[str, str, str], list[str]] = {}
        self._notifications: dict[tuple[str, str, str], ObjectiveNotification] = {}
        self._dedupe: set[tuple[str, str, str, str]] = set()
        self._lock = threading.RLock()

    def upsert_objective(
        self, ctx: ControlPlaneContext, *, objective: DeliveryObjective
    ) -> DeliveryObjective:
        key = (*_scope(ctx), objective.objective_id)
        if (
            objective.tenant_id != ctx.tenant.tenant_id
            or objective.workspace_id != ctx.workspace.workspace_id
        ):
            raise ControlPlaneError.forbidden("objective scope mismatch")
        with self._lock:
            self._objectives[key] = objective
            return deepcopy(objective)

    def get_objective(
        self, ctx: ControlPlaneContext, *, objective_id: str
    ) -> DeliveryObjective:
        with self._lock:
            obj = self._objectives.get((*_scope(ctx), objective_id))
            if obj is None:
                raise ControlPlaneError.not_found("objective not found")
            return deepcopy(obj)

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
        evaluated_at = now or _now()
        with self._lock:
            objective = self.get_objective(ctx, objective_id=objective_id)
            warning_at = objective.deadline(reference_at, hard=False)
            hard_at = objective.deadline(reference_at, hard=True)
            if completed:
                # Recovery if previously breached for this submission.
                state = "recovered"
                reason = "completed within recovery"
            elif evaluated_at >= hard_at:
                state = "breached"
                reason = "hard deadline missed"
            elif evaluated_at >= warning_at:
                state = "warning"
                reason = "warning deadline reached"
            else:
                state = "on_track"
                reason = "within deadlines"
            dedupe_key = f"{objective_id}:{state}:{submission_id or 'none'}"
            scope = (*_scope(ctx), dedupe_key)
            if scope in self._dedupe and state in ("breached", "warning", "recovered"):
                # Return prior evaluation for the same transition.
                for eid in self._by_objective.get((*_scope(ctx), objective_id), []):
                    prior = self._evaluations.get((*_scope(ctx), eid))
                    if prior and prior.dedupe_key == dedupe_key:
                        return deepcopy(prior)
            evaluation = ObjectiveEvaluation(
                evaluation_id=str(uuid.uuid4()),
                objective_id=objective_id,
                state=state,  # type: ignore[arg-type]
                reference_at=reference_at,
                evaluated_at=evaluated_at,
                dedupe_key=dedupe_key,
                submission_id=submission_id,
                reason=reason,
            )
            self._evaluations[(*_scope(ctx), evaluation.evaluation_id)] = evaluation
            self._by_objective.setdefault((*_scope(ctx), objective_id), []).append(
                evaluation.evaluation_id
            )
            if state in ("breached", "warning", "recovered"):
                self._dedupe.add(scope)
            return deepcopy(evaluation)

    def acknowledge(
        self,
        ctx: ControlPlaneContext,
        *,
        evaluation_id: str,
    ) -> ObjectiveEvaluation:
        with self._lock:
            key = (*_scope(ctx), evaluation_id)
            evaluation = self._evaluations.get(key)
            if evaluation is None:
                raise ControlPlaneError.not_found("evaluation not found")
            updated = replace(evaluation, state="acknowledged")
            self._evaluations[key] = updated
            return deepcopy(updated)

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
        with self._lock:
            evaluation = self._evaluations.get((*_scope(ctx), evaluation_id))
            if evaluation is None:
                raise ControlPlaneError.not_found("evaluation not found")
            if destination_ref not in authorized_destinations:
                raise ControlPlaneError.forbidden(
                    "notification destination not authorized",
                    extensions={"destination_ref": destination_ref},
                )
            if provider.channel != channel:
                raise ControlPlaneError.conflict("notification channel mismatch")
            delivered = provider.deliver(
                ctx,
                destination_ref=destination_ref,
                subject=f"objective {evaluation.objective_id} {evaluation.state}",
                body={
                    "evaluation_id": evaluation.evaluation_id,
                    "state": evaluation.state,
                    "dedupe_key": evaluation.dedupe_key,
                },
            )
            note = ObjectiveNotification(
                notification_id=str(uuid.uuid4()),
                evaluation_id=evaluation_id,
                channel=channel,
                destination_ref=destination_ref,
                delivered=delivered,
            )
            self._notifications[(*_scope(ctx), note.notification_id)] = note
            return deepcopy(note)

    def list_evaluations(
        self, ctx: ControlPlaneContext, *, objective_id: str, limit: int = 100
    ) -> Sequence[ObjectiveEvaluation]:
        with self._lock:
            ids = self._by_objective.get((*_scope(ctx), objective_id), [])
            out = []
            for eid in ids[-limit:]:
                ev = self._evaluations.get((*_scope(ctx), eid))
                if ev is not None:
                    out.append(deepcopy(ev))
            return out


__all__ = [
    "MemoryNotificationProvider",
    "MemoryObjectiveStore",
    "memory_email_provider",
    "memory_incident_provider",
    "memory_slack_provider",
    "memory_webhook_provider",
]
