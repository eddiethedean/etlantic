# pyright: reportUnknownArgumentType=false, reportUnknownVariableType=false
"""Versioned schedule and firing records with checked legacy readers."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from etlantic.control_plane.durable_models import validate_execution_route
from etlantic.control_plane.models import Principal
from etlantic.control_plane.redaction import (
    redact_control_plane_payload,
    redact_control_plane_text,
)
from etlantic.control_plane.schedule_diagnostics import fire_diagnostic
from etlantic.secrets.ref import SecretRef

SCHEDULE_SCHEMA = "etlantic.schedule/3"
FIRING_SCHEMA = "etlantic.firing/4"

_SCHEDULE_FIELDS = frozenset(
    {
        "schema",
        "schedule_id",
        "definition_id",
        "revision_id",
        "tenant_id",
        "workspace_id",
        "profile_name",
        "policy_fingerprint",
        "spec",
        "created_at",
        "updated_at",
        "status",
        "next_fire_at",
        "definition_revision_id",
        "parameter_refs",
        "secret_refs",
        "metadata",
        "revision_policy",
        "workload_identity",
        "execution_route",
        "timer_owner",
        "timer_owner_generation",
        "timer_revision_policy",
        "timer_schedule_start_at",
        "timer_binding_fingerprint",
    }
)
_FIRING_FIELDS = frozenset(
    {
        "schema",
        "firing_id",
        "schedule_id",
        "revision_id",
        "nominal_fire_time",
        "tenant_id",
        "workspace_id",
        "created_at",
        "status",
        "submission_id",
        "metadata",
        "logical_key",
        "preparation_owner_id",
        "preparation_fencing_token",
        "preparation_expires_at",
        "submission_started",
        "submission_attempt_ids",
    }
)

ScheduleKind = Literal["interval", "cron"]
ScheduleStatus = Literal["active", "paused", "deleted"]
MisfirePolicy = Literal["skip", "fire_once", "catch_up"]
OverlapPolicy = Literal["skip", "queue"]
FiringStatus = Literal[
    "accepted",
    "skipped_overlap",
    "skipped_misfire",
    "skipped_window",
    "failed_preparation",
]
ScheduleRevisionPolicy = Literal["pinned", "latest-approved"]
TimerOwner = Literal["local", "external"]

FORBIDDEN_SCHEDULE_KEYS = frozenset(
    {"payload", "secret", "password", "token", "row", "event", "body"}
)


def _metadata(value: Mapping[str, Any] | None) -> dict[str, Any]:
    result = redact_control_plane_payload(dict(value or {}))
    return dict(result) if isinstance(result, dict) else {}


def _timer_owner(value: object) -> TimerOwner:
    if not isinstance(value, str) or value not in ("local", "external"):
        raise ValueError("schedule timer_owner must be local or external")
    return value


def _revision_policy(value: object) -> ScheduleRevisionPolicy:
    if not isinstance(value, str) or value not in ("pinned", "latest-approved"):
        raise ValueError("schedule revision_policy is unsupported")
    return value


def assert_schedule_payload_clean(data: Mapping[str, Any]) -> None:
    """Fail closed when schedule artifacts contain payload/secret tokens."""
    hits: list[str] = []

    def _walk(node: Any, prefix: str) -> None:
        if isinstance(node, dict):
            for key, val in node.items():
                lower = str(key).lower()
                path = f"{prefix}.{key}" if prefix else str(key)
                if lower in FORBIDDEN_SCHEDULE_KEYS:
                    hits.append(path)
                is_secret_reference = path.startswith("secret_refs.")
                if (
                    isinstance(val, str)
                    and not is_secret_reference
                    and any(token in val.lower() for token in ("payload", "secret"))
                ):
                    hits.append(path)
                _walk(val, path)
        elif isinstance(node, list):
            for i, item in enumerate(node):
                _walk(item, f"{prefix}[{i}]")

    _walk(data, "")
    refs = data.get("secret_refs")
    if refs is not None:
        if not isinstance(refs, Mapping):
            hits.append("secret_refs")
        else:
            for alias, raw_ref in refs.items():
                if not isinstance(alias, str) or not isinstance(raw_ref, Mapping):
                    if isinstance(alias, str) and isinstance(raw_ref, str):
                        # Older reference schedules used opaque URI strings.
                        # Managed schedules require structured SecretRef values.
                        if "://" not in raw_ref or "@" in raw_ref or "?" in raw_ref:
                            hits.append(f"secret_refs.{alias}")
                        continue
                    hits.append(f"secret_refs.{alias}")
                    continue
                try:
                    allowed = {"provider", "name", "key", "version", "purpose"}
                    if set(raw_ref) - allowed:
                        raise ValueError("unexpected reference fields")
                    SecretRef.from_dict(dict(raw_ref))
                except (KeyError, TypeError, ValueError):
                    hits.append(f"secret_refs.{alias}")
    if hits:
        diag = fire_diagnostic(
            "payload_leak",
            "Schedule artifacts must not contain payload or secret tokens: "
            + ", ".join(hits[:8]),
            path=("schedule",),
        )
        raise ValueError(f"{diag.code}: {diag.message}")


def firing_key(schedule_id: str, revision_id: str, nominal_fire_time: str) -> str:
    """Canonical logical firing identity."""
    sid = schedule_id.strip()
    rev = revision_id.strip()
    nom = nominal_fire_time.strip()
    if not sid or not rev or not nom:
        raise ValueError("firing key parts must be non-empty")
    return f"{sid}:{rev}:{nom}"


@dataclass(frozen=True, slots=True)
class ScheduleSpec:
    """Versioned interval or cron schedule with explicit time policy."""

    kind: ScheduleKind
    timezone: str = "UTC"
    interval_seconds: int | None = None
    cron: str | None = None
    misfire: MisfirePolicy = "fire_once"
    catch_up_max: int = 10
    overlap: OverlapPolicy = "skip"
    jitter_seconds: int = 0
    window_start: str | None = None
    window_end: str | None = None

    def __post_init__(self) -> None:
        timezone_value: object = cast(object, self.timezone)
        if not isinstance(timezone_value, str) or not timezone_value.strip():
            raise ValueError("schedule timezone must be non-empty")
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("schedule timezone must be a known IANA zone") from exc
        if type(self.catch_up_max) is not int or self.catch_up_max < 0:
            raise ValueError("catch_up_max must be >= 0")
        if type(self.jitter_seconds) is not int or self.jitter_seconds < 0:
            raise ValueError("jitter_seconds must be >= 0")
        if self.misfire not in ("skip", "fire_once", "catch_up"):
            raise ValueError("schedule misfire policy is unsupported")
        if self.overlap not in ("skip", "queue"):
            raise ValueError("schedule overlap policy is unsupported")
        if self.kind == "interval":
            if type(self.interval_seconds) is not int or self.interval_seconds <= 0:
                raise ValueError("interval schedules require interval_seconds > 0")
        elif self.kind == "cron":
            if not isinstance(self.cron, str) or not self.cron.strip():
                raise ValueError("cron schedules require a 5-field cron expression")
        else:
            raise ValueError(f"unsupported schedule kind: {self.kind}")
        for name in ("window_start", "window_end"):
            value = getattr(self, name)
            if value is None:
                continue
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"schedule {name} must be a timestamp when set")
            try:
                moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError(f"schedule {name} must be ISO-8601") from exc
            if moment.tzinfo is None or moment.utcoffset() is None:
                raise ValueError(f"schedule {name} must include a timezone")
        if self.window_start is not None and self.window_end is not None:
            start = datetime.fromisoformat(self.window_start.replace("Z", "+00:00"))
            end = datetime.fromisoformat(self.window_end.replace("Z", "+00:00"))
            if start >= end:
                raise ValueError("schedule window_start must precede window_end")

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "timezone": self.timezone,
            "interval_seconds": self.interval_seconds,
            "cron": self.cron,
            "misfire": self.misfire,
            "catch_up_max": self.catch_up_max,
            "overlap": self.overlap,
            "jitter_seconds": self.jitter_seconds,
            "window_start": self.window_start,
            "window_end": self.window_end,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ScheduleSpec:
        return cls(
            kind=data["kind"],
            timezone=data.get("timezone") or "UTC",
            interval_seconds=data.get("interval_seconds"),
            cron=data.get("cron"),
            misfire=data.get("misfire") or "fire_once",
            catch_up_max=(
                10 if data.get("catch_up_max") is None else data["catch_up_max"]
            ),
            overlap=data.get("overlap") or "skip",
            jitter_seconds=(
                0 if data.get("jitter_seconds") is None else data["jitter_seconds"]
            ),
            window_start=data.get("window_start"),
            window_end=data.get("window_end"),
        )


@dataclass(frozen=True, slots=True)
class ScheduleRecord:
    """Secret-free schedule revision stored by :class:`ScheduleStore`."""

    schedule_id: str
    definition_id: str
    revision_id: str
    tenant_id: str
    workspace_id: str
    profile_name: str
    policy_fingerprint: str
    spec: ScheduleSpec
    created_at: str
    updated_at: str
    status: ScheduleStatus = "active"
    next_fire_at: str | None = None
    # Managed schedules pin an immutable definition revision at creation.
    # Legacy/reference schedule stores may leave this unset.
    definition_revision_id: str | None = None
    parameter_refs: Mapping[str, str] = field(default_factory=dict)
    secret_refs: Mapping[str, Mapping[str, Any] | str] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    revision_policy: ScheduleRevisionPolicy = "pinned"
    workload_identity: Principal | None = None
    # Managed occurrences inherit the route selected when this revision was
    # created. Older schedule snapshots default to local polling.
    execution_route: str = "local"
    # Runtime-only values are attached after an occurrence has been claimed.
    # They are never emitted by to_dict or persisted in the schedule snapshot.
    occurrence_snapshot: Mapping[str, Any] | None = field(
        default=None, repr=False, compare=False
    )
    occurrence_inputs: Mapping[str, Any] | None = field(
        default=None, repr=False, compare=False
    )
    # Invoked at admission; returns cleanup for a definite CP1 rejection only.
    occurrence_acceptance_guard: Callable[[], Callable[[], None] | None] | None = field(
        default=None, repr=False, compare=False
    )
    # Invoked only after CP1 cancellation and a verified CP3 miss following a
    # definite durable-admission rejection.
    occurrence_compensation_guard: Callable[[], None] | None = field(
        default=None, repr=False, compare=False
    )
    # Owner changes use the generation-fenced transfer operation. Existing
    # records without these fields remain locally owned at generation one.
    timer_owner: TimerOwner = "local"
    timer_owner_generation: int = 1
    # Stable remote recurrence anchor; unlike next_fire_at it never advances.
    timer_schedule_start_at: str | None = None
    # Opaque durable digest of a timer adapter's immutable target configuration.
    timer_binding_fingerprint: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "schedule_id",
            "definition_id",
            "revision_id",
            "tenant_id",
            "workspace_id",
            "profile_name",
            "created_at",
            "updated_at",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"schedule {name} must be non-empty")
        if self.status not in ("active", "paused", "deleted"):
            raise ValueError("schedule status is unsupported")
        if self.revision_policy not in ("pinned", "latest-approved"):
            raise ValueError("schedule revision_policy is unsupported")
        if self.timer_owner not in ("local", "external"):
            raise ValueError("schedule timer_owner must be local or external")
        if (
            type(self.timer_owner_generation) is not int
            or self.timer_owner_generation < 1
        ):
            raise ValueError("schedule timer_owner_generation must be positive")
        if self.occurrence_acceptance_guard is not None and not callable(
            self.occurrence_acceptance_guard
        ):
            raise ValueError("occurrence_acceptance_guard must be callable")
        if self.occurrence_compensation_guard is not None and not callable(
            self.occurrence_compensation_guard
        ):
            raise ValueError("occurrence_compensation_guard must be callable")
        validate_execution_route(self.execution_route)
        workload_identity: object = cast(object, self.workload_identity)
        if workload_identity is not None:
            if not isinstance(workload_identity, Principal):
                raise ValueError("schedule workload_identity must be a Principal")
            if workload_identity.kind not in ("workload", "service"):
                raise ValueError(
                    "schedule workload_identity must be workload or service"
                )
        if self.timer_owner == "external" and self.workload_identity is None:
            raise ValueError("externally owned schedule requires a workload identity")
        if self.timer_schedule_start_at is not None:
            try:
                anchor = datetime.fromisoformat(
                    self.timer_schedule_start_at.replace("Z", "+00:00")
                )
            except (AttributeError, TypeError, ValueError) as exc:
                raise ValueError("schedule timer anchor must be ISO-8601") from exc
            if anchor.tzinfo is None or anchor.utcoffset() is None:
                raise ValueError("schedule timer anchor must be timezone aware")
            if (
                anchor.microsecond
                or anchor.astimezone(UTC).isoformat().replace("+00:00", "Z")
                != self.timer_schedule_start_at
            ):
                raise ValueError(
                    "schedule timer anchor must be canonical UTC with whole seconds"
                )
            if self.timer_owner != "external":
                raise ValueError(
                    "local schedules cannot persist an external timer anchor"
                )
        if self.timer_binding_fingerprint is not None:
            fingerprint: object = cast(object, self.timer_binding_fingerprint)
            if (
                not isinstance(fingerprint, str)
                or re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None
            ):
                raise ValueError(
                    "timer binding fingerprint must be a lowercase SHA-256 value"
                )
            if self.timer_owner != "external":
                raise ValueError(
                    "local schedules cannot persist an external timer binding"
                )
        if self.next_fire_at is not None:
            try:
                next_fire = datetime.fromisoformat(
                    self.next_fire_at.replace("Z", "+00:00")
                )
            except (AttributeError, TypeError, ValueError) as exc:
                raise ValueError("schedule next_fire_at must be ISO-8601") from exc
            if next_fire.tzinfo is None or next_fire.utcoffset() is None:
                raise ValueError("schedule next_fire_at must include a timezone")

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema": SCHEDULE_SCHEMA,
            "schedule_id": self.schedule_id,
            "definition_id": self.definition_id,
            "revision_id": self.revision_id,
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
            "profile_name": self.profile_name,
            "policy_fingerprint": self.policy_fingerprint,
            "spec": self.spec.to_dict(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "next_fire_at": self.next_fire_at,
            "definition_revision_id": self.definition_revision_id,
            "parameter_refs": dict(self.parameter_refs),
            "secret_refs": dict(self.secret_refs),
            "metadata": _metadata(self.metadata),
            "revision_policy": self.revision_policy,
            "workload_identity": (
                self.workload_identity.to_dict()
                if self.workload_identity is not None
                else None
            ),
            "execution_route": self.execution_route,
            "timer_owner": self.timer_owner,
            "timer_owner_generation": self.timer_owner_generation,
        }
        if self.timer_schedule_start_at is not None:
            payload["timer_schedule_start_at"] = self.timer_schedule_start_at
        if self.timer_binding_fingerprint is not None:
            payload["timer_binding_fingerprint"] = self.timer_binding_fingerprint
        assert_schedule_payload_clean(payload)
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ScheduleRecord:
        schema = data.get("schema")
        if schema not in (
            None,
            "etlantic.schedule/1",
            "etlantic.schedule/2",
            SCHEDULE_SCHEMA,
        ):
            raise ValueError(f"unsupported schedule schema: {schema!r}")
        if set(data) - _SCHEDULE_FIELDS:
            raise ValueError("schedule record contains unsupported fields")
        assert_schedule_payload_clean(data)
        timer_owner = _timer_owner(data.get("timer_owner", "local"))
        revision_policy_value: object = data.get("revision_policy") or "pinned"
        if revision_policy_value == "external_timer_owned":
            if timer_owner != "external":
                raise ValueError("external timer rollback fence is inconsistent")
            revision_policy_value = data.get("timer_revision_policy") or ""
        elif revision_policy_value == "admission_fenced":
            if timer_owner != "local":
                raise ValueError("local admission rollback fence is inconsistent")
            revision_policy_value = data.get("timer_revision_policy") or ""
        revision_policy = _revision_policy(revision_policy_value)
        return cls(
            schedule_id=data["schedule_id"],
            definition_id=data["definition_id"],
            revision_id=data["revision_id"],
            tenant_id=data["tenant_id"],
            workspace_id=data["workspace_id"],
            profile_name=data["profile_name"],
            policy_fingerprint=data.get("policy_fingerprint") or "",
            spec=ScheduleSpec.from_dict(data["spec"]),
            created_at=str(data["created_at"]),
            updated_at=str(data["updated_at"]),
            status=data.get("status") or "active",
            next_fire_at=data.get("next_fire_at"),
            definition_revision_id=(
                data["definition_revision_id"]
                if data.get("definition_revision_id") is not None
                else None
            ),
            parameter_refs=dict(data.get("parameter_refs") or {}),
            secret_refs={
                str(name): dict(value) if isinstance(value, Mapping) else str(value)
                for name, value in dict(data.get("secret_refs") or {}).items()
            },
            metadata=_metadata(data.get("metadata")),
            revision_policy=revision_policy,
            workload_identity=(
                Principal.from_dict(data["workload_identity"])
                if isinstance(data.get("workload_identity"), Mapping)
                else None
            ),
            execution_route=validate_execution_route(
                data.get("execution_route", "local")
            ),
            timer_owner=timer_owner,
            timer_owner_generation=data.get("timer_owner_generation", 1),
            timer_schedule_start_at=data.get("timer_schedule_start_at"),
            timer_binding_fingerprint=data.get("timer_binding_fingerprint"),
        )


@dataclass(frozen=True, slots=True)
class FiringRecord:
    """Idempotent logical firing accepted into durable work."""

    firing_id: str
    schedule_id: str
    revision_id: str
    nominal_fire_time: str
    tenant_id: str
    workspace_id: str
    created_at: str
    status: FiringStatus = "accepted"
    submission_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    preparation_owner_id: str | None = field(default=None, repr=False, compare=False)
    preparation_fencing_token: int = field(default=0, repr=False, compare=False)
    preparation_expires_at: str | None = field(default=None, repr=False, compare=False)
    # A started admission may still commit after its preparation lease expires.
    submission_started: bool = field(default=False, repr=False, compare=False)
    submission_attempt_ids: tuple[str, ...] = field(
        default=(), repr=False, compare=False
    )

    def __post_init__(self) -> None:
        for name in (
            "firing_id",
            "schedule_id",
            "revision_id",
            "nominal_fire_time",
            "tenant_id",
            "workspace_id",
            "created_at",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"firing {name} must be non-empty")
        if self.status not in (
            "accepted",
            "skipped_overlap",
            "skipped_misfire",
            "skipped_window",
            "failed_preparation",
        ):
            raise ValueError("firing status is unsupported")
        for name in ("nominal_fire_time", "created_at"):
            try:
                moment = datetime.fromisoformat(
                    getattr(self, name).replace("Z", "+00:00")
                )
            except ValueError as exc:
                raise ValueError(f"firing {name} must be ISO-8601") from exc
            if moment.tzinfo is None or moment.utcoffset() is None:
                raise ValueError(f"firing {name} must include a timezone")
        submission_id: object = cast(object, self.submission_id)
        if submission_id is not None and (
            not isinstance(submission_id, str) or not submission_id.strip()
        ):
            raise ValueError("firing submission_id must be non-empty when set")
        if type(self.preparation_fencing_token) is not int or (
            self.preparation_fencing_token < 0
        ):
            raise ValueError("firing preparation_fencing_token must be non-negative")
        if type(self.submission_started) is not bool:
            raise ValueError("firing submission_started must be a boolean")
        raw_attempt_ids: object = cast(object, self.submission_attempt_ids)
        if (
            not isinstance(raw_attempt_ids, tuple)
            or any(
                not isinstance(attempt, str) or not attempt.strip()
                for attempt in cast(tuple[object, ...], raw_attempt_ids)
            )
            or len(set(self.submission_attempt_ids)) != len(self.submission_attempt_ids)
            or (self.submission_attempt_ids and not self.submission_started)
        ):
            raise ValueError(
                "firing submission attempt IDs must be unique non-empty strings with submission_started"
            )
        if (self.preparation_owner_id is None) != (self.preparation_expires_at is None):
            raise ValueError("firing preparation lease fields must be paired")
        preparation_owner_id: object = cast(object, self.preparation_owner_id)
        preparation_expires_at: object = cast(object, self.preparation_expires_at)
        if preparation_owner_id is not None:
            if (
                not isinstance(preparation_owner_id, str)
                or not preparation_owner_id.strip()
            ):
                raise ValueError("firing preparation owner must be non-empty")
            if not isinstance(preparation_expires_at, str):
                raise ValueError("firing preparation expiry must be non-empty")
            try:
                expiry = datetime.fromisoformat(
                    preparation_expires_at.replace("Z", "+00:00")
                )
            except (AttributeError, ValueError) as exc:
                raise ValueError("firing preparation expiry must be ISO-8601") from exc
            if expiry.tzinfo is None or expiry.utcoffset() is None:
                raise ValueError("firing preparation expiry must include a timezone")

    @property
    def logical_key(self) -> str:
        return firing_key(self.schedule_id, self.revision_id, self.nominal_fire_time)

    def to_dict(self) -> dict[str, Any]:
        """Return a caller-safe firing representation without the prep lease."""
        values = asdict(self)
        values.pop("preparation_owner_id", None)
        values.pop("preparation_fencing_token", None)
        values.pop("preparation_expires_at", None)
        values.pop("submission_started", None)
        values.pop("submission_attempt_ids", None)
        payload = {
            "schema": FIRING_SCHEMA,
            **values,
            "logical_key": self.logical_key,
            "metadata": _metadata(self.metadata),
        }
        payload["created_at"] = redact_control_plane_text(self.created_at)
        assert_schedule_payload_clean(payload)
        return payload

    def to_storage_dict(self) -> dict[str, Any]:
        """Return the complete durable row, including internal admission state."""
        payload = {
            "schema": FIRING_SCHEMA,
            **asdict(self),
            "logical_key": self.logical_key,
            "metadata": _metadata(self.metadata),
        }
        payload["created_at"] = redact_control_plane_text(self.created_at)
        assert_schedule_payload_clean(payload)
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> FiringRecord:
        schema = data.get("schema")
        if schema not in (
            None,
            "etlantic.firing/1",
            "etlantic.firing/2",
            "etlantic.firing/3",
            FIRING_SCHEMA,
        ):
            raise ValueError(f"unsupported firing schema: {schema!r}")
        if set(data) - _FIRING_FIELDS:
            raise ValueError("firing record contains unsupported fields")
        assert_schedule_payload_clean(data)
        preparation_token = data.get("preparation_fencing_token", 0)
        if type(preparation_token) is not int or preparation_token < 0:
            raise ValueError("firing preparation_fencing_token must be non-negative")
        submission_started = data.get("submission_started", False)
        if type(submission_started) is not bool:
            raise ValueError("firing submission_started must be a boolean")
        submission_attempt_ids = data.get("submission_attempt_ids", ())
        if not isinstance(submission_attempt_ids, (list, tuple)):
            raise ValueError("firing submission attempt IDs must be a sequence")
        attempt_ids: list[str] = []
        for attempt in cast(list[object] | tuple[object, ...], submission_attempt_ids):
            if not isinstance(attempt, str) or not attempt.strip():
                raise ValueError("firing submission attempt ID must be non-empty")
            attempt_ids.append(attempt)
        preparation_owner = data.get("preparation_owner_id")
        preparation_expiry = data.get("preparation_expires_at")
        if (preparation_owner is None) != (preparation_expiry is None):
            raise ValueError("firing preparation lease fields must be paired")
        if preparation_owner is not None:
            if not isinstance(preparation_owner, str) or not preparation_owner.strip():
                raise ValueError("firing preparation owner must be non-empty")
            if (
                not isinstance(preparation_expiry, str)
                or not preparation_expiry.strip()
            ):
                raise ValueError("firing preparation expiry must be non-empty")
            try:
                expiry = datetime.fromisoformat(
                    preparation_expiry.replace("Z", "+00:00")
                )
            except ValueError as exc:
                raise ValueError("firing preparation expiry must be ISO-8601") from exc
            if expiry.tzinfo is None or expiry.utcoffset() is None:
                raise ValueError("firing preparation expiry must include a timezone")
        record = cls(
            firing_id=data["firing_id"],
            schedule_id=data["schedule_id"],
            revision_id=data["revision_id"],
            nominal_fire_time=data["nominal_fire_time"],
            tenant_id=data["tenant_id"],
            workspace_id=data["workspace_id"],
            created_at=data["created_at"],
            status=data.get("status") or "accepted",
            submission_id=data.get("submission_id"),
            metadata=_metadata(data.get("metadata")),
            preparation_owner_id=(
                data["preparation_owner_id"]
                if data.get("preparation_owner_id") is not None
                else None
            ),
            preparation_fencing_token=preparation_token,
            preparation_expires_at=(
                data["preparation_expires_at"]
                if data.get("preparation_expires_at") is not None
                else None
            ),
            submission_started=submission_started,
            submission_attempt_ids=tuple(attempt_ids),
        )
        logical_key = data.get("logical_key")
        if logical_key is not None and logical_key != record.logical_key:
            raise ValueError("firing logical_key does not match its identity fields")
        return record
