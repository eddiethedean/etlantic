"""EventBridge Scheduler to canonical HTTPS trigger relay."""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from importlib.metadata import EntryPoint, entry_points
from typing import Any, cast

from etlantic.control_plane import ScheduleRecord
from etlantic_rsconnect import (
    HttpsTriggerDelivery,
    OccurrenceContext,
    build_trigger_envelope,
)

from etlantic_aws.scheduler import EventBridgeScheduler

_ENTRY_POINT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_EVENT_FIELDS = frozenset(
    {
        "schema",
        "schedule_id",
        "schedule_revision_id",
        "timer_owner_generation",
        "schedule_arn",
        "scheduled_at",
        "execution_id",
        "attempt_number",
    }
)
_EVENT_SCHEMA = "etlantic.aws.scheduler_invocation/1"


class RelayRetryRequired(RuntimeError):
    """The canonical receipt is pending or delivery needs a Lambda retry."""


class ScheduledTriggerRelay:
    """Validate Scheduler context against current durable ownership and relay it.

    ``get_schedule`` must resolve the schedule from the same durable store used
    by the receiver. It must not trust fields from the Scheduler event as the
    schedule record.
    """

    def __init__(
        self,
        scheduler: EventBridgeScheduler,
        delivery: HttpsTriggerDelivery,
        get_schedule: Callable[[str], ScheduleRecord],
    ) -> None:
        if not isinstance(cast(object, scheduler), EventBridgeScheduler):
            raise TypeError("scheduler must be an EventBridgeScheduler")
        if not isinstance(cast(object, delivery), HttpsTriggerDelivery):
            raise TypeError("delivery must be an HttpsTriggerDelivery")
        if not callable(get_schedule):
            raise TypeError("get_schedule must be callable")
        self.scheduler = scheduler
        self.delivery = delivery
        self.get_schedule = get_schedule

    def handle_event(self, event: Mapping[str, Any]) -> dict[str, Any]:
        """Deliver one authenticated-by-context scheduler occurrence."""
        event_value: object = cast(object, event)
        if not isinstance(event_value, Mapping):
            raise ValueError("Scheduler event must be an object")
        event_data = cast(Mapping[str, Any], event_value)
        if frozenset(event_data.keys()) != _EVENT_FIELDS:
            raise ValueError("Scheduler event has unknown or missing fields")
        if event_data.get("schema") != _EVENT_SCHEMA:
            raise ValueError("Scheduler event schema is unsupported")
        schedule_id = _bounded_text(event_data.get("schedule_id"), "schedule_id", 512)
        revision_id = _bounded_text(
            event_data.get("schedule_revision_id"), "schedule_revision_id", 512
        )
        generation = event_data.get("timer_owner_generation")
        if type(generation) is not int or generation < 1:
            raise ValueError("timer_owner_generation must be a positive integer")
        execution_id = _bounded_text(
            event_data.get("execution_id"), "execution_id", 256
        )
        attempt_number = _attempt_number(event_data.get("attempt_number"))
        schedule_arn = _bounded_text(
            event_data.get("schedule_arn"), "schedule_arn", 1024
        )
        record = self.get_schedule(schedule_id)
        if (
            record.schedule_id != schedule_id
            or record.timer_owner != "external"
            or record.workload_identity is None
        ):
            raise ValueError("Scheduler event does not match durable ownership")
        if schedule_arn != self.scheduler.schedule_arn(record):
            raise ValueError("Scheduler ARN does not match the registered schedule")

        scheduled_at = _canonical_utc(event_data.get("scheduled_at"))
        delivery_attempt_id = f"aws-scheduler:{execution_id}:{attempt_number}"
        correlation_id = f"aws-scheduler:{execution_id}"
        occurrence = OccurrenceContext(
            scheduled_at=scheduled_at,
            delivery_attempt_id=delivery_attempt_id,
            correlation_id=correlation_id,
        )
        envelope = build_trigger_envelope(
            schedule_id=schedule_id,
            schedule_revision_id=revision_id,
            timer_owner_generation=generation,
            occurrence=occurrence,
        )
        receipt = self.delivery.reconcile(envelope)
        if receipt is not None and receipt.status in {"accepted", "skipped"}:
            return receipt.to_dict()
        if (
            record.revision_id != revision_id
            or record.timer_owner_generation != generation
            or (receipt is None and record.status != "active")
        ):
            raise ValueError("Scheduler event is stale for the durable schedule")
        result = self.delivery.deliver(envelope)
        if result.receipt.status == "pending":
            raise RelayRetryRequired("canonical trigger admission is still pending")
        return result.receipt.to_dict()


def load_trusted_relay(name: str) -> ScheduledTriggerRelay:
    """Load exactly one preinstalled relay factory from the trusted entry-point group."""
    name_value: object = cast(object, name)
    if not isinstance(name_value, str) or _ENTRY_POINT.fullmatch(name_value) is None:
        raise RuntimeError("trusted AWS relay is not configured")
    matches: tuple[EntryPoint, ...] = tuple(
        entry_points(group="etlantic.aws_schedule_relays", name=name_value)
    )
    if len(matches) != 1:
        raise RuntimeError("configured AWS relay is unavailable or ambiguous")
    factory = matches[0].load()
    if not callable(factory):
        raise RuntimeError("configured AWS relay factory is invalid")
    relay = factory()
    if not isinstance(relay, ScheduledTriggerRelay):
        raise RuntimeError("AWS relay factory returned an invalid relay")
    return relay


def lambda_handler(event: Mapping[str, Any], context: Any = None) -> dict[str, Any]:
    """AWS Lambda handler; all authority is supplied by the trusted factory."""
    del context
    name = os.environ.get("ETLANTIC_AWS_SCHEDULE_RELAY")
    return load_trusted_relay(name or "").handle_event(event)


def _bounded_text(value: object, name: str, limit: int) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > limit
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        raise ValueError(f"{name} must be bounded printable text")
    return value


def _attempt_number(value: object) -> int:
    if isinstance(value, str) and re.fullmatch(r"[1-9][0-9]{0,8}", value):
        return int(value)
    if type(value) is int and 1 <= value <= 999_999_999:
        return value
    raise ValueError("attempt_number must be a positive bounded integer")


def _canonical_utc(value: object) -> str:
    if not isinstance(value, str) or len(value) > 64:
        raise ValueError("scheduled_at must be a bounded ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("scheduled_at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("scheduled_at must include a timezone")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


__all__ = [
    "RelayRetryRequired",
    "ScheduledTriggerRelay",
    "lambda_handler",
    "load_trusted_relay",
]
