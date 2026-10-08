"""Public lifecycle facts for supervised scheduler and worker roles."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from typing import Literal

RoleKind = Literal["scheduler", "run_worker", "action_worker"]
Activity = Literal["idle", "active", "standby"]
Admission = Literal["accepting", "draining", "stopped"]
Prerequisites = Literal["unknown", "usable", "unusable"]
_SAFE_REASON_CODES = frozenset(
    {
        "not_yet_observed",
        "leader_lease_held",
        "scheduler_tick_failed",
        "schedule_store_unavailable",
        "schedule_dispatch_failed",
        "occurrence_recovery_failed",
        "worker_tick_failed",
        "lease_store_unavailable",
        "action_lease_lost",
        "result_publication_unavailable",
        "external_condition",
    }
)


@dataclass(frozen=True, slots=True)
class RuntimeRoleStatus:
    """Secret-free local role state; this is not a workload health probe."""

    role: RoleKind
    activity: Activity
    admission: Admission
    prerequisites: Prerequisites
    reason_code: str | None
    in_flight: int
    observed_at: str
    capabilities: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return self.admission == "accepting" and self.prerequisites == "usable"

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "etlantic.runtime_role_status/1",
            "role": self.role,
            "activity": self.activity,
            "admission": self.admission,
            "prerequisites": self.prerequisites,
            "reason_code": self.reason_code,
            "in_flight": self.in_flight,
            "observed_at": self.observed_at,
            "capabilities": list(self.capabilities),
            "ready": self.ready,
        }


class RuntimeRoleLifecycle:
    """Thread-safe stop gate and cached status for one role instance."""

    def __init__(self, role: RoleKind, *, capabilities: tuple[str, ...]) -> None:
        self.role: RoleKind = role
        self.capabilities = capabilities
        self._lock = Lock()
        self._draining = False
        self._stopped = False
        self._tick_active = False
        self._in_flight = 0
        self._standby = False
        self._prerequisites: Prerequisites = "unknown"
        self._reason_code: str | None = "not_yet_observed"
        self._observed_at = datetime.now(UTC)

    @property
    def draining(self) -> bool:
        with self._lock:
            return self._draining

    def request_drain(self) -> RuntimeRoleStatus:
        """Stop new ticks and claims immediately; already-dispatched work may finish."""
        with self._lock:
            self._draining = True
            if not self._tick_active and self._in_flight == 0:
                self._stopped = True
            self._observe()
            return self._snapshot()

    def begin_tick(self) -> bool:
        """Reserve the single tick slot without holding locks across I/O."""
        with self._lock:
            if self._draining or self._tick_active:
                return False
            self._tick_active = True
            self._in_flight += 1
            self._standby = False
            self._stopped = False
            self._observe()
            return True

    def end_tick(self) -> None:
        with self._lock:
            self._tick_active = False
            if self._in_flight:
                self._in_flight -= 1
            if self._draining and self._in_flight == 0:
                self._stopped = True
            self._observe()

    def begin_dispatch(self) -> bool:
        """Reserve an imminent claim; drain does not block while provider I/O runs."""
        with self._lock:
            if self._draining or not self._tick_active:
                return False
            self._in_flight += 1
            self._observe()
            return True

    def end_dispatch(self) -> None:
        with self._lock:
            if self._in_flight:
                self._in_flight -= 1
            if self._draining and not self._tick_active and self._in_flight == 0:
                self._stopped = True
            self._observe()

    def begin_background_operation(self) -> None:
        """Track an owned monitor that may outlive its caller's bounded wait."""
        with self._lock:
            self._in_flight += 1
            self._observe()

    def end_background_operation(self) -> None:
        with self._lock:
            if self._in_flight:
                self._in_flight -= 1
            if self._draining and not self._tick_active and self._in_flight == 0:
                self._stopped = True
            self._observe()

    def observe_prerequisites(
        self,
        state: Prerequisites,
        *,
        reason_code: str | None = None,
    ) -> None:
        with self._lock:
            self._prerequisites = state
            self._reason_code = _safe_reason(reason_code)
            self._observe()

    def observe_standby(self, reason_code: str | None = None) -> None:
        with self._lock:
            self._standby = True
            self._prerequisites = "usable"
            self._reason_code = _safe_reason(reason_code or "leader_lease_held")
            self._observe()

    def status(self) -> RuntimeRoleStatus:
        """Return a local snapshot; performs no store, lease, or secret operation."""
        with self._lock:
            return self._snapshot()

    def _snapshot(self) -> RuntimeRoleStatus:
        admission: Admission = (
            "stopped"
            if self._stopped
            else "draining"
            if self._draining
            else "accepting"
        )
        activity: Activity = (
            "active"
            if self._tick_active or self._in_flight
            else "standby"
            if self._standby
            else "idle"
        )
        return RuntimeRoleStatus(
            role=self.role,
            activity=activity,
            admission=admission,
            prerequisites=self._prerequisites,
            reason_code=self._reason_code,
            in_flight=self._in_flight,
            observed_at=self._observed_at.isoformat().replace("+00:00", "Z"),
            capabilities=self.capabilities,
        )

    def _observe(self) -> None:
        self._observed_at = datetime.now(UTC)


def _safe_reason(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or value not in _SAFE_REASON_CODES:
        return "external_condition"
    return value


__all__ = [
    "Activity",
    "Admission",
    "Prerequisites",
    "RoleKind",
    "RuntimeRoleLifecycle",
    "RuntimeRoleStatus",
]
