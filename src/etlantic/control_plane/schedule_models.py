# pyright: reportUnknownArgumentType=false, reportUnknownVariableType=false
"""Schedule and firing records (`etlantic.schedule/1`, `etlantic.firing/1`)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from etlantic.control_plane.models import Principal
from etlantic.control_plane.redaction import (
    redact_control_plane_payload,
    redact_control_plane_text,
)
from etlantic.control_plane.schedule_diagnostics import fire_diagnostic
from etlantic.secrets.ref import SecretRef

SCHEDULE_SCHEMA = "etlantic.schedule/1"
FIRING_SCHEMA = "etlantic.firing/1"

ScheduleKind = Literal["interval", "cron"]
ScheduleStatus = Literal["active", "paused", "deleted"]
MisfirePolicy = Literal["skip", "fire_once", "catch_up"]
OverlapPolicy = Literal["skip", "queue"]
FiringStatus = Literal[
    "accepted", "skipped_overlap", "skipped_misfire", "skipped_window"
]
ScheduleRevisionPolicy = Literal["pinned", "latest-approved"]

FORBIDDEN_SCHEDULE_KEYS = frozenset(
    {"payload", "secret", "password", "token", "row", "event", "body"}
)


def _metadata(value: Mapping[str, Any] | None) -> dict[str, Any]:
    result = redact_control_plane_payload(dict(value or {}))
    return dict(result) if isinstance(result, dict) else {}


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
        if self.catch_up_max < 0:
            raise ValueError("catch_up_max must be >= 0")
        if self.jitter_seconds < 0:
            raise ValueError("jitter_seconds must be >= 0")
        if self.kind == "interval":
            if self.interval_seconds is None or int(self.interval_seconds) <= 0:
                raise ValueError("interval schedules require interval_seconds > 0")
        elif self.kind == "cron":
            if not (self.cron or "").strip():
                raise ValueError("cron schedules require a 5-field cron expression")
        else:
            raise ValueError(f"unsupported schedule kind: {self.kind}")

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
            kind=str(data["kind"]),  # type: ignore[arg-type]
            timezone=str(data.get("timezone") or "UTC"),
            interval_seconds=(
                int(data["interval_seconds"])
                if data.get("interval_seconds") is not None
                else None
            ),
            cron=data.get("cron"),
            misfire=str(data.get("misfire") or "fire_once"),  # type: ignore[arg-type]
            catch_up_max=int(
                10 if data.get("catch_up_max") is None else data["catch_up_max"]
            ),
            overlap=str(data.get("overlap") or "skip"),  # type: ignore[arg-type]
            jitter_seconds=int(data.get("jitter_seconds") or 0),
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
    # Runtime-only values are attached after an occurrence has been claimed.
    # They are never emitted by to_dict or persisted in the schedule snapshot.
    occurrence_snapshot: Mapping[str, Any] | None = field(
        default=None, repr=False, compare=False
    )
    occurrence_inputs: Mapping[str, Any] | None = field(
        default=None, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        if self.revision_policy not in ("pinned", "latest-approved"):
            raise ValueError("schedule revision_policy is unsupported")
        if self.workload_identity is not None and self.workload_identity.kind not in (
            "workload",
            "service",
        ):
            raise ValueError("schedule workload_identity must be workload or service")

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
        }
        assert_schedule_payload_clean(payload)
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ScheduleRecord:
        assert_schedule_payload_clean(data)
        return cls(
            schedule_id=str(data["schedule_id"]),
            definition_id=str(data["definition_id"]),
            revision_id=str(data["revision_id"]),
            tenant_id=str(data["tenant_id"]),
            workspace_id=str(data["workspace_id"]),
            profile_name=str(data["profile_name"]),
            policy_fingerprint=str(data.get("policy_fingerprint") or ""),
            spec=ScheduleSpec.from_dict(data["spec"]),
            created_at=str(data["created_at"]),
            updated_at=str(data["updated_at"]),
            status=str(data.get("status") or "active"),  # type: ignore[arg-type]
            next_fire_at=data.get("next_fire_at"),
            definition_revision_id=(
                str(data["definition_revision_id"])
                if data.get("definition_revision_id") is not None
                else None
            ),
            parameter_refs=dict(data.get("parameter_refs") or {}),
            secret_refs={
                str(name): dict(value) if isinstance(value, Mapping) else str(value)
                for name, value in dict(data.get("secret_refs") or {}).items()
            },
            metadata=_metadata(data.get("metadata")),
            revision_policy=str(data.get("revision_policy") or "pinned"),  # type: ignore[arg-type]
            workload_identity=(
                Principal.from_dict(data["workload_identity"])
                if isinstance(data.get("workload_identity"), Mapping)
                else None
            ),
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

    @property
    def logical_key(self) -> str:
        return firing_key(self.schedule_id, self.revision_id, self.nominal_fire_time)

    def to_dict(self) -> dict[str, Any]:
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
        assert_schedule_payload_clean(data)
        return cls(
            firing_id=str(data["firing_id"]),
            schedule_id=str(data["schedule_id"]),
            revision_id=str(data["revision_id"]),
            nominal_fire_time=str(data["nominal_fire_time"]),
            tenant_id=str(data["tenant_id"]),
            workspace_id=str(data["workspace_id"]),
            created_at=str(data["created_at"]),
            status=str(data.get("status") or "accepted"),  # type: ignore[arg-type]
            submission_id=data.get("submission_id"),
            metadata=_metadata(data.get("metadata")),
        )
