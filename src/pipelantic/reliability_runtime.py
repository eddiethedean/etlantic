"""Runtime reliability enforcement helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pipelantic.exceptions import PipelineExecutionError
from pipelantic.reliability import (
    BackfillDeclaration,
    FreshnessExpectation,
    PartitionCompletenessExpectation,
    RepairDeclaration,
    RetrySafetyDeclaration,
    WriteMode,
)
from pipelantic.runtime.request import InvalidationMode, RunIntent, RunRequest


@dataclass(frozen=True, slots=True)
class BackfillRequest:
    """Runtime backfill request derived from intent/declaration."""

    subject_id: str
    start: str | None = None
    end: str | None = None
    partitions: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_declaration(cls, decl: BackfillDeclaration) -> BackfillRequest:
        return cls(
            subject_id=decl.subject_id,
            start=decl.start,
            end=decl.end,
            partitions=decl.partitions,
            metadata=dict(decl.metadata),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "start": self.start,
            "end": self.end,
            "partitions": list(self.partitions),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class FreshnessCheckResult:
    subject_id: str
    ok: bool
    age_seconds: float | None = None
    message: str | None = None


def check_freshness(
    expectation: FreshnessExpectation,
    *,
    observed_at: datetime | None,
    now: datetime | None = None,
) -> FreshnessCheckResult:
    """Local freshness check against a declared expectation."""
    if expectation.max_age_seconds is None:
        return FreshnessCheckResult(subject_id=expectation.subject_id, ok=True)
    if observed_at is None:
        return FreshnessCheckResult(
            subject_id=expectation.subject_id,
            ok=False,
            message="No observed timestamp available for freshness check",
        )
    current = now or datetime.now(UTC)
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=UTC)
    age = (current - observed_at).total_seconds()
    limit = expectation.max_age_seconds + expectation.grace_seconds
    ok = age <= limit
    return FreshnessCheckResult(
        subject_id=expectation.subject_id,
        ok=ok,
        age_seconds=age,
        message=None if ok else f"Data age {age:.1f}s exceeds limit {limit:.1f}s",
    )


def check_partition_completeness(
    expectation: PartitionCompletenessExpectation,
    *,
    observed_partitions: set[str] | frozenset[str],
    expected_partitions: set[str] | frozenset[str] | None = None,
) -> tuple[bool, str | None]:
    if (
        expectation.minimum_count is not None
        and len(observed_partitions) < expectation.minimum_count
    ):
        return (
            False,
            f"Observed {len(observed_partitions)} partitions; "
            f"minimum {expectation.minimum_count}",
        )
    if expected_partitions is not None:
        missing = set(expected_partitions) - set(observed_partitions)
        if missing:
            return False, f"Missing partitions: {', '.join(sorted(missing))}"
    return True, None


def assert_retry_safe(
    declaration: RetrySafetyDeclaration | None,
    *,
    attempt: int,
    step_name: str,
    run_id: str,
) -> None:
    if declaration is None:
        return
    if not declaration.safe and attempt > 1:
        raise PipelineExecutionError(
            f"Retry refused for {step_name}: retry-safety declares unsafe "
            f"(attempt={attempt}).",
            run_id=run_id,
            code="PMEXEC501",
        )
    if declaration.max_attempts is not None and attempt > declaration.max_attempts:
        raise PipelineExecutionError(
            f"Retry refused for {step_name}: exceeded max_attempts "
            f"{declaration.max_attempts}.",
            run_id=run_id,
            code="PMEXEC502",
        )


def minimum_safe_repair(
    *,
    failed_nodes: set[str],
    downstream: dict[str, set[str]],
) -> RepairDeclaration:
    """Compute minimum-safe repair closure from failed nodes."""
    affected: set[str] = set(failed_nodes)
    stack = list(failed_nodes)
    while stack:
        node = stack.pop()
        for child in downstream.get(node, ()):
            if child not in affected:
                affected.add(child)
                stack.append(child)
    return RepairDeclaration(
        subject_id="run",
        reason="minimum_safe_repair",
        affected_nodes=tuple(sorted(affected)),
    )


def invalidation_targets(
    *,
    graph_nodes: list[str],
    target: str,
    mode: InvalidationMode,
    downstream: dict[str, set[str]],
) -> set[str]:
    if mode is InvalidationMode.NONE:
        return set()
    if mode is InvalidationMode.TARGET:
        return {target}
    if mode is InvalidationMode.DOWNSTREAM:
        affected = {target}
        stack = [target]
        while stack:
            node = stack.pop()
            for child in downstream.get(node, ()):
                if child not in affected:
                    affected.add(child)
                    stack.append(child)
        return affected
    # CLOSURE: everything from target through end of declaration order
    if target not in graph_nodes:
        return {target}
    idx = graph_nodes.index(target)
    return set(graph_nodes[idx:])


def write_mode_for_request(request: RunRequest) -> WriteMode:
    if request.no_write or request.intent is RunIntent.VALIDATE:
        return WriteMode.NO_WRITE
    return WriteMode.OVERWRITE
