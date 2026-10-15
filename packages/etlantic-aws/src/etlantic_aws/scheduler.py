"""EventBridge Scheduler lifecycle over durable ETLantic schedule records."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from typing import Any, cast

from etlantic.control_plane.schedule_models import ScheduleRecord

_VERSIONED_LAMBDA = re.compile(
    r"^arn:(aws|aws-us-gov):lambda:([a-z0-9-]+):([0-9]{12}):function:[A-Za-z0-9_-]+:[1-9][0-9]*$"
)


def schedule_name(schedule_id: str) -> str:
    """Return a stable AWS-safe name without disclosing the canonical ID."""
    schedule_id_value: object = cast(object, schedule_id)
    if not isinstance(schedule_id_value, str) or not schedule_id_value.strip():
        raise ValueError("schedule_id must be non-empty")
    return "etl-" + hashlib.sha256(schedule_id.encode("utf-8")).hexdigest()[:60]


class EventBridgeScheduler:
    """One-account/region Scheduler binding with disabled-first activation."""

    def __init__(
        self,
        client: Any,
        *,
        account_id: str,
        region: str,
        group_name: str,
        lambda_version_arn: str,
        scheduler_role_arn: str,
        dlq_arn: str,
        mutation_guard: Callable[[ScheduleRecord], AbstractContextManager[Any]],
        maximum_event_age_seconds: int = 3600,
        maximum_retry_attempts: int = 2,
    ) -> None:
        if not re.fullmatch(r"[0-9]{12}", account_id):
            raise ValueError("account_id must be a 12 digit AWS account")
        target = _VERSIONED_LAMBDA.fullmatch(lambda_version_arn)
        if target is None or target.group(2) != region or target.group(3) != account_id:
            raise ValueError(
                "lambda_version_arn must pin a version in this account/region"
            )
        partition = target.group(1)
        expected_partition = "aws-us-gov" if region.startswith("us-gov-") else "aws"
        if partition != expected_partition:
            raise ValueError(
                "Lambda ARN partition does not match the configured region"
            )
        if not scheduler_role_arn.startswith(
            f"arn:{partition}:iam::{account_id}:role/"
        ):
            raise ValueError("scheduler role must belong to the configured account")
        if not dlq_arn.startswith(f"arn:{partition}:sqs:{region}:{account_id}:"):
            raise ValueError(
                "DLQ must be an SQS queue in the configured account/region"
            )
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", group_name):
            raise ValueError("group_name must be an existing explicit schedule group")
        if (
            type(maximum_event_age_seconds) is not int
            or not 60 <= maximum_event_age_seconds <= 86_400
        ):
            raise ValueError("maximum_event_age_seconds must be between 60 and 86400")
        if (
            type(maximum_retry_attempts) is not int
            or not 0 <= maximum_retry_attempts <= 185
        ):
            raise ValueError("maximum_retry_attempts must be between 0 and 185")
        self.client = client
        self.account_id = account_id
        self.region = region
        self.group_name = group_name
        self.lambda_version_arn = lambda_version_arn
        self.scheduler_role_arn = scheduler_role_arn
        self.dlq_arn = dlq_arn
        if not callable(mutation_guard):
            raise TypeError(
                "mutation_guard must provide durable schedule serialization"
            )
        self.mutation_guard = mutation_guard
        self.maximum_event_age_seconds = maximum_event_age_seconds
        self.maximum_retry_attempts = maximum_retry_attempts

    @property
    def binding_fingerprint(self) -> str:
        """Digest the durable timer binding without persisting AWS credentials."""
        payload = {
            "schema": "etlantic.aws.scheduler_binding/1",
            "account_id": self.account_id,
            "region": self.region,
            "group_name": self.group_name,
            "lambda_version_arn": self.lambda_version_arn,
            "scheduler_role_arn": self.scheduler_role_arn,
            "dlq_arn": self.dlq_arn,
            "maximum_event_age_seconds": self.maximum_event_age_seconds,
            "maximum_retry_attempts": self.maximum_retry_attempts,
        }
        encoded = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def schedule_arn(self, record: ScheduleRecord) -> str:
        partition = "aws-us-gov" if self.region.startswith("us-gov-") else "aws"
        return (
            f"arn:{partition}:scheduler:{self.region}:{self.account_id}:schedule/"
            f"{self.group_name}/{schedule_name(record.schedule_id)}"
        )

    def create_disabled(self, record: ScheduleRecord) -> Mapping[str, Any]:
        """Create or verify an owned disabled schedule for an external owner."""
        self._validate_record(record)
        return self._with_mutation_guard(record, lambda: self._create_disabled(record))

    def _create_disabled(self, record: ScheduleRecord) -> Mapping[str, Any]:
        desired = self._request(record, state="DISABLED")
        try:
            self.client.create_schedule(**desired)
        except Exception:
            # Create may have committed before a lost response or name conflict.
            observed = self._read(record)
            self._assert_matches(record, observed, expected_state="DISABLED")
            return observed
        observed = self._read(record)
        self._assert_matches(record, observed, expected_state="DISABLED")
        return observed

    def activate(self, record: ScheduleRecord) -> Mapping[str, Any]:
        """Enable only a complete, readback-verified disabled schedule."""
        self._validate_record(record)
        self._require_future_cursor(record)
        return self._with_mutation_guard(record, lambda: self._activate(record))

    def _activate(self, record: ScheduleRecord) -> Mapping[str, Any]:
        prior = self._read(record)
        self._assert_matches(record, prior, expected_state="DISABLED")
        desired = self._request(record, state="ENABLED")
        try:
            self.client.update_schedule(**desired)
        except Exception:
            observed = self._read(record)
            self._assert_matches(record, observed, expected_state="ENABLED")
            return observed
        observed = self._read(record)
        self._assert_matches(record, observed, expected_state="ENABLED")
        return observed

    def pause(self, record: ScheduleRecord) -> Mapping[str, Any]:
        """Disable only after verifying that the remote resource is still owned."""
        self._validate_record(record, allow_paused=True)
        return self._with_mutation_guard(record, lambda: self._pause(record))

    def _pause(self, record: ScheduleRecord) -> Mapping[str, Any]:
        observed = self._read(record)
        self._assert_matches(record, observed)
        try:
            self.client.update_schedule(**self._request(record, state="DISABLED"))
        except Exception:
            observed = self._read(record)
            self._assert_matches(record, observed, expected_state="DISABLED")
            return observed
        observed = self._read(record)
        self._assert_matches(record, observed, expected_state="DISABLED")
        return observed

    def resume(self, record: ScheduleRecord) -> Mapping[str, Any]:
        """Re-enable a verified schedule at the same revision/generation."""
        self._validate_record(record)
        self._require_future_cursor(record)
        return self._with_mutation_guard(record, lambda: self._resume(record))

    def _resume(self, record: ScheduleRecord) -> Mapping[str, Any]:
        observed = self._read(record)
        self._assert_matches(record, observed, expected_state="DISABLED")
        try:
            self.client.update_schedule(**self._request(record, state="ENABLED"))
        except Exception:
            observed = self._read(record)
            self._assert_matches(record, observed, expected_state="ENABLED")
            return observed
        observed = self._read(record)
        self._assert_matches(record, observed, expected_state="ENABLED")
        return observed

    def delete(self, record: ScheduleRecord) -> None:
        """Delete only the fully matching, deterministic resource owned here."""
        self._validate_record(record, allow_deleted=True, allow_paused=True)
        self._with_mutation_guard(record, lambda: self._delete(record))

    def _delete(self, record: ScheduleRecord) -> None:
        observed = self._read(record)
        self._assert_matches(record, observed)
        try:
            self.client.delete_schedule(
                Name=schedule_name(record.schedule_id), GroupName=self.group_name
            )
        except Exception:
            if self._read_optional(record) is not None:
                raise RuntimeError(
                    "owned schedule deletion outcome is uncertain"
                ) from None

    def update_disabled(
        self, previous: ScheduleRecord, replacement: ScheduleRecord
    ) -> Mapping[str, Any]:
        """Disable and replace one owned revision, leaving it disabled.

        The caller must persist the replacement revision before invoking this
        method, then call :meth:`activate` only after the canonical transition
        is complete. A failure leaves the remote schedule disabled whenever
        the first update succeeded.
        """
        self._validate_record(previous, allow_paused=True)
        self._validate_record(replacement, allow_paused=True)
        self._require_future_cursor(replacement)
        if previous.schedule_id != replacement.schedule_id:
            raise ValueError("schedule revisions must have the same schedule_id")
        if previous.timer_binding_fingerprint != replacement.timer_binding_fingerprint:
            raise ValueError(
                "timer binding changes require a separately fenced migration"
            )
        return self._with_mutation_guard(
            previous, lambda: self._update_disabled(previous, replacement)
        )

    def _update_disabled(
        self, previous: ScheduleRecord, replacement: ScheduleRecord
    ) -> Mapping[str, Any]:
        observed = self._read(previous)
        self._assert_matches(previous, observed)
        if observed.get("State") != "DISABLED":
            try:
                self.client.update_schedule(**self._request(previous, state="DISABLED"))
            except Exception:
                observed = self._read(previous)
                self._assert_matches(previous, observed, expected_state="DISABLED")
            else:
                observed = self._read(previous)
                self._assert_matches(previous, observed, expected_state="DISABLED")
        try:
            self.client.update_schedule(**self._request(replacement, state="DISABLED"))
        except Exception:
            observed = self._read(replacement)
            self._assert_matches(replacement, observed, expected_state="DISABLED")
            return observed
        observed = self._read(replacement)
        self._assert_matches(replacement, observed, expected_state="DISABLED")
        return observed

    def _with_mutation_guard(
        self, record: ScheduleRecord, operation: Callable[[], Any]
    ):
        with self.mutation_guard(record):
            return operation()

    def _request(self, record: ScheduleRecord, *, state: str) -> dict[str, Any]:
        spec = record.spec
        if spec.kind != "interval" or spec.interval_seconds is None:
            raise ValueError("initial AWS schedule support requires an interval")
        if (
            spec.timezone != "UTC"
            or spec.interval_seconds < 60
            or spec.interval_seconds % 60
            or spec.jitter_seconds != 0
            or spec.window_start is not None
            or spec.window_end is not None
            or spec.misfire not in {"skip", "fire_once"}
            or spec.catch_up_max != 10
        ):
            raise ValueError("schedule recurrence is outside the qualified AWS matrix")
        interval_minutes = spec.interval_seconds // 60
        unit = "minute" if interval_minutes == 1 else "minutes"
        schedule_expression = f"rate({interval_minutes} {unit})"
        raw_anchor = record.timer_schedule_start_at
        if not isinstance(raw_anchor, str):
            raise ValueError("AWS scheduling requires a durable timer start anchor")
        try:
            anchor = datetime.fromisoformat(raw_anchor.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(
                "timer anchor must be an aware ISO-8601 timestamp"
            ) from exc
        if anchor.tzinfo is None or anchor.utcoffset() is None:
            raise ValueError("timer anchor must be timezone aware")
        anchor = anchor.astimezone(UTC)
        if anchor.microsecond:
            raise ValueError("timer anchor must have whole-second precision")
        scheduled_input = {
            "schema": "etlantic.aws.scheduler_invocation/1",
            "schedule_id": record.schedule_id,
            "schedule_revision_id": record.revision_id,
            "timer_owner_generation": record.timer_owner_generation,
            "schedule_arn": "<aws.scheduler.schedule-arn>",
            "scheduled_at": "<aws.scheduler.scheduled-time>",
            "execution_id": "<aws.scheduler.execution-id>",
            "attempt_number": "<aws.scheduler.attempt-number>",
        }
        return {
            "Name": schedule_name(record.schedule_id),
            "GroupName": self.group_name,
            "ScheduleExpression": schedule_expression,
            "ScheduleExpressionTimezone": "UTC",
            "StartDate": anchor,
            "FlexibleTimeWindow": {"Mode": "OFF"},
            "State": state,
            "Target": {
                "Arn": self.lambda_version_arn,
                "RoleArn": self.scheduler_role_arn,
                "Input": json.dumps(
                    scheduled_input,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ),
                "DeadLetterConfig": {"Arn": self.dlq_arn},
                "RetryPolicy": {
                    "MaximumEventAgeInSeconds": self.maximum_event_age_seconds,
                    "MaximumRetryAttempts": self.maximum_retry_attempts,
                },
            },
        }

    def _validate_record(
        self,
        record: ScheduleRecord,
        *,
        allow_paused: bool = False,
        allow_deleted: bool = False,
    ) -> None:
        if record.timer_owner != "external" or record.workload_identity is None:
            raise ValueError(
                "AWS schedule requires a registered external workload owner"
            )
        if record.timer_binding_fingerprint != self.binding_fingerprint:
            raise ValueError(
                "durable schedule timer binding does not match this adapter"
            )
        if record.status == "paused" and not allow_paused:
            raise ValueError("paused schedule cannot be activated")
        if record.status == "deleted" and not allow_deleted:
            raise ValueError("deleted schedule cannot be activated")
        if record.status not in ({"active", "paused", "deleted"}):
            raise ValueError("schedule state is unsupported")

    @staticmethod
    def _require_future_cursor(record: ScheduleRecord) -> None:
        value = record.next_fire_at
        if not isinstance(value, str):
            raise ValueError("AWS scheduling requires a durable next-fire cursor")
        try:
            next_fire = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(
                "next_fire_at must be an aware ISO-8601 timestamp"
            ) from exc
        if next_fire.tzinfo is None or next_fire.utcoffset() is None:
            raise ValueError("next_fire_at must be timezone aware")
        if next_fire.astimezone(UTC) <= datetime.now(UTC):
            raise ValueError(
                "external schedule cursor is overdue; re-anchor before activation"
            )

    def _read_optional(self, record: ScheduleRecord) -> Mapping[str, Any] | None:
        try:
            result = self.client.get_schedule(
                Name=schedule_name(record.schedule_id), GroupName=self.group_name
            )
        except Exception as exc:
            response_value: object = getattr(exc, "response", {})
            if isinstance(response_value, Mapping):
                response = cast(Mapping[str, Any], response_value)
                error_value: object = response.get("Error", {})
            else:
                error_value = {}
            error: Mapping[str, Any] = {}
            if isinstance(error_value, Mapping):
                error = cast(Mapping[str, Any], error_value)
            if error.get("Code") in {"ResourceNotFoundException", "ResourceNotFound"}:
                return None
            raise RuntimeError("schedule observation is unavailable") from None
        return result

    def _read(self, record: ScheduleRecord) -> Mapping[str, Any]:
        observed = self._read_optional(record)
        if observed is None:
            raise RuntimeError("owned schedule is absent")
        return observed

    def _assert_matches(
        self,
        record: ScheduleRecord,
        observed: Mapping[str, Any],
        *,
        expected_state: str | None = None,
    ) -> None:
        desired = self._request(
            record, state=expected_state or str(observed.get("State"))
        )
        target_value: object = observed.get("Target")
        target: Mapping[str, Any] | None = None
        if isinstance(target_value, Mapping):
            target = cast(Mapping[str, Any], target_value)
        expected_target = desired["Target"]
        exact: bool = bool(
            observed.get("State") in {"ENABLED", "DISABLED"}
            and observed.get("Arn") == self.schedule_arn(record)
            and observed.get("Name") == desired["Name"]
            and observed.get("GroupName") == desired["GroupName"]
            and observed.get("ScheduleExpression") == desired["ScheduleExpression"]
            and observed.get("ScheduleExpressionTimezone", "UTC") == "UTC"
            and _timestamp_matches(observed.get("StartDate"), desired["StartDate"])
            and observed.get("EndDate") is None
            and observed.get("FlexibleTimeWindow") == {"Mode": "OFF"}
            and target is not None
            and target.get("Arn") == expected_target["Arn"]
            and target.get("RoleArn") == expected_target["RoleArn"]
            and target.get("Input") == expected_target["Input"]
            and target.get("DeadLetterConfig") == expected_target["DeadLetterConfig"]
            and target.get("RetryPolicy") == expected_target["RetryPolicy"]
        )
        if not exact or (
            expected_state is not None and observed.get("State") != expected_state
        ):
            raise RuntimeError(
                "remote schedule is drifted or not owned by this binding"
            )


def _timestamp_matches(actual: object, expected: datetime) -> bool:
    if not isinstance(actual, datetime) or actual.tzinfo is None:
        return False
    return actual.astimezone(UTC) == expected.astimezone(UTC)


__all__ = ["EventBridgeScheduler", "schedule_name"]
