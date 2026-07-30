"""Application-pipeline testing preview helpers (ETLantic 0.35).

Available (preview): typed cases, fakes, plan/report snapshots, and a
validate → plan → run → normalize path for independently maintained pipelines.
Full graduation of this foundation is planned for 0.38.

Security invariants:

- fixtures are static logical rows only
- snapshots and case results must not contain resolved secret values
- secret providers used here return only fixture-declared values
- snapshot files are never overwritten unless ``update=True`` is explicit
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from contextlib import asynccontextmanager, nullcontext
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.plan.model import PipelinePlan
from etlantic.plan.serialize import canonical_plan_dict
from etlantic.profile import Profile
from etlantic.reports.model import PipelineRunReport
from etlantic.runtime.faults import FaultSpec
from etlantic.runtime.state import RunStatus
from etlantic.secrets.provider import (
    ProviderContext,
    SecretProviderCapabilities,
    SecretProviderDescriptor,
    SecretResolutionContext,
)
from etlantic.secrets.ref import SecretRef
from etlantic.secrets.value import SecretValue
from etlantic.testing.faults import with_faults

PipelineTarget = type | Any


@dataclass(frozen=True, slots=True)
class ExpectedResult:
    """Expected outcome for a pipeline test case (preview).

    Attributes:
        status: Expected run status (``succeeded``, ``failed``, …).
        records_out: Optional expected total records_out from the run summary.
        diagnostic_codes: Optional codes that must appear in the run report.
        sink_assets: Optional mapping of asset name → expected logical row dicts.
    """

    status: str = "succeeded"
    records_out: int | None = None
    diagnostic_codes: tuple[str, ...] = ()
    sink_assets: Mapping[str, tuple[Mapping[str, Any], ...]] = field(
        default_factory=dict
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "records_out": self.records_out,
            "diagnostic_codes": list(self.diagnostic_codes),
            "sink_assets": {
                key: [dict(row) for row in rows]
                for key, rows in dict(self.sink_assets).items()
            },
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ExpectedResult:
        sinks_raw = data.get("sink_assets") or {}
        sinks = {
            str(k): tuple(dict(row) for row in (v or ()))
            for k, v in dict(sinks_raw).items()
        }
        codes = tuple(str(c) for c in (data.get("diagnostic_codes") or ()))
        return cls(
            status=str(data.get("status") or "succeeded"),
            records_out=(
                int(data["records_out"])
                if data.get("records_out") is not None
                else None
            ),
            diagnostic_codes=codes,
            sink_assets=sinks,
        )


@dataclass(frozen=True, slots=True)
class PipelineTestCase:
    """Typed, deterministic, serializable application-pipeline test case (preview).

    Attributes:
        case_id: Stable case identity.
        pipeline: Pipeline class (or object exposing validate/plan/run).
        profile: Profile name or ``Profile`` instance.
        seed: Mapping of memory asset → static logical row mappings/objects.
        expected: Expected outcome.
        faults: Optional fault specs bound for the duration of the case.
        metadata: Secret-free case metadata.
    """

    case_id: str
    pipeline: PipelineTarget
    profile: str | Profile = "development"
    seed: Mapping[str, Sequence[Any]] = field(default_factory=dict)
    expected: ExpectedResult = field(default_factory=ExpectedResult)
    faults: tuple[FaultSpec, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        pipe_name = getattr(self.pipeline, "__name__", type(self.pipeline).__name__)
        profile_ref = (
            self.profile.name
            if isinstance(self.profile, Profile)
            else str(self.profile)
        )
        return {
            "case_id": self.case_id,
            "pipeline": pipe_name,
            "profile": profile_ref,
            "seed_assets": sorted(self.seed),
            "seed_counts": {k: len(v) for k, v in dict(self.seed).items()},
            "expected": self.expected.to_dict(),
            "faults": [
                {
                    "boundary": str(f.boundary),
                    "message": f.message,
                    "trigger": str(f.trigger),
                    "step_name": f.step_name,
                }
                for f in self.faults
            ],
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class FakeClock:
    """Deterministic clock for pipeline tests (preview)."""

    instant: datetime = field(
        default_factory=lambda: datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    )

    def now(self) -> datetime:
        return self.instant


@dataclass(frozen=True, slots=True)
class FakeRunIdentity:
    """Deterministic run identity (preview)."""

    run_id: str = "test-run-0001"
    pipeline_id: str | None = None

    def next_run_id(self) -> str:
        return self.run_id


class FakeSecretProvider:
    """Fixture-only secret provider (preview).

    Resolves only names declared in ``values``. Never contacts external systems.
    Resolved values must not be written into plans/reports by callers.
    """

    def __init__(self, values: Mapping[str, str] | None = None) -> None:
        self._values = {str(k): str(v) for k, v in dict(values or {}).items()}
        self.descriptor = SecretProviderDescriptor(
            name="fake",
            engine="fake",
            version="0.36.0",
            capabilities=SecretProviderCapabilities(in_memory_cache=True),
        )

    @asynccontextmanager
    async def lifespan(self, context: ProviderContext):  # type: ignore[no-untyped-def]
        yield

    async def resolve(
        self,
        reference: SecretRef,
        context: SecretResolutionContext,
    ) -> SecretValue:
        name = reference.name
        if name not in self._values:
            raise LookupError(f"FakeSecretProvider has no fixture value for {name!r}")
        return SecretValue(name=name, value=self._values[name])


@dataclass(frozen=True, slots=True)
class PipelineCaseResult:
    """Normalized result of ``run_pipeline_case`` (preview)."""

    case_id: str
    status: str
    plan: dict[str, Any]
    report: dict[str, Any]
    ok: bool
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "status": self.status,
            "plan": self.plan,
            "report": self.report,
            "ok": self.ok,
            "errors": list(self.errors),
        }


def _normalize_report(report: PipelineRunReport) -> dict[str, Any]:
    data = report.to_dict()
    # Drop volatile timestamps for snapshot stability.
    data.pop("started_at", None)
    data.pop("ended_at", None)
    data.pop("duration_seconds", None)
    for step in data.get("steps") or []:
        step.pop("started_at", None)
        step.pop("ended_at", None)
        step.pop("duration_seconds", None)
    for transition in data.get("state_transitions") or []:
        transition.pop("at", None)
        transition.pop("timestamp", None)
    _assert_no_resolved_secrets(data, path="report")
    return data


def _normalize_plan(plan: PipelinePlan) -> dict[str, Any]:
    data = canonical_plan_dict(plan)
    _assert_no_resolved_secrets(data, path="plan")
    return data


def _assert_no_resolved_secrets(value: Any, *, path: str) -> None:
    """Fail closed on secret-like keys; ignore bare core report/plan keys."""
    from etlantic.extensions import _URL_USERINFO_VALUE_RE, _is_secret_like_key

    if isinstance(value, dict):
        for key, child in value.items():
            if _is_secret_like_key(str(key)):
                raise ValueError(f"{path} contains forbidden secret-like key {key!r}")
            _assert_no_resolved_secrets(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_no_resolved_secrets(item, path=f"{path}[{index}]")
    elif isinstance(value, str) and _URL_USERINFO_VALUE_RE.search(value):
        raise ValueError(f"{path} contains a URL with userinfo credentials")


def _rows_as_dicts(rows: Sequence[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, Mapping):
            out.append(dict(row))
        elif hasattr(row, "model_dump"):
            out.append(dict(row.model_dump()))
        elif hasattr(row, "__dict__"):
            out.append({k: v for k, v in vars(row).items() if not k.startswith("_")})
        else:
            raise TypeError(f"Unsupported seed row type: {type(row)!r}")
    return out


def snapshot_plan(
    plan: PipelinePlan | Mapping[str, Any],
    path: str | Path,
    *,
    update: bool = False,
) -> dict[str, Any]:
    """Write or load a plan snapshot. Never overwrites unless ``update=True``."""
    target = Path(path)
    payload = _normalize_plan(plan) if isinstance(plan, PipelinePlan) else dict(plan)
    _assert_no_resolved_secrets(payload, path="snapshot_plan")
    if update:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return payload
    if not target.exists():
        raise FileNotFoundError(
            f"Plan snapshot missing at {target}; pass update=True to create it"
        )
    return json.loads(target.read_text(encoding="utf-8"))


def snapshot_report(
    report: PipelineRunReport | Mapping[str, Any],
    path: str | Path,
    *,
    update: bool = False,
) -> dict[str, Any]:
    """Write or load a report snapshot. Never overwrites unless ``update=True``."""
    target = Path(path)
    payload = (
        _normalize_report(report)
        if isinstance(report, PipelineRunReport)
        else dict(report)
    )
    _assert_no_resolved_secrets(payload, path="snapshot_report")
    if update:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return payload
    if not target.exists():
        raise FileNotFoundError(
            f"Report snapshot missing at {target}; pass update=True to create it"
        )
    return json.loads(target.read_text(encoding="utf-8"))


def assert_snapshots_match(
    actual: Mapping[str, Any],
    expected: Mapping[str, Any],
    *,
    path: str = "snapshot",
) -> None:
    """Assert two snapshot mappings are equal (sorted JSON compare)."""
    left = json.dumps(actual, sort_keys=True, separators=(",", ":"))
    right = json.dumps(expected, sort_keys=True, separators=(",", ":"))
    if left != right:
        raise AssertionError(f"Snapshot mismatch at {path}")


def run_pipeline_case(
    case: PipelineTestCase,
    *,
    profile: str | Profile | None = None,
    runtime: PipelineRuntime | None = None,
    identity: FakeRunIdentity | None = None,
) -> PipelineCaseResult:
    """Validate → plan → run → normalize a pipeline test case (preview).

    Args:
        case: Typed test case with static seed rows.
        profile: Optional profile override.
        runtime: Optional runtime (defaults to a fresh ``PipelineRuntime``).
        identity: Optional fake run identity (metadata only for preview).

    Returns:
        ``PipelineCaseResult`` with normalized plan/report and ``ok`` flag.
    """
    pipe = case.pipeline
    resolved_profile: str | Profile = profile if profile is not None else case.profile
    rt = runtime or PipelineRuntime()
    errors: list[str] = []
    plan_blob: dict[str, Any] = {}
    report_blob: dict[str, Any] = {}
    status = "failed"
    fault_ctx = with_faults(*case.faults) if case.faults else nullcontext()
    with fault_ctx:
        try:
            validation = pipe.validate(profile=resolved_profile)
            has_errors = getattr(validation, "has_errors", False)
            if callable(has_errors):
                has_errors = has_errors()
            if has_errors:
                errors.append(
                    validation.to_text()
                    if hasattr(validation, "to_text")
                    else str(validation)
                )
            plan = pipe.plan(profile=resolved_profile)
            plan_blob = _normalize_plan(plan)
            for asset, rows in dict(case.seed).items():
                rt.memory.seed(asset, list(rows))
            report = pipe.run(profile=resolved_profile, runtime=rt)
            report_blob = _normalize_report(report)
            status = (
                report.status.value
                if hasattr(report.status, "value")
                else str(report.status)
            )
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
            status = "failed"

    expected = case.expected
    if status != expected.status:
        errors.append(f"status {status!r} != expected {expected.status!r}")
    if expected.records_out is not None and report_blob:
        actual_out = (report_blob.get("summary") or {}).get("records_out")
        if actual_out != expected.records_out:
            errors.append(
                f"records_out {actual_out!r} != expected {expected.records_out!r}"
            )
    if expected.diagnostic_codes and report_blob:
        codes = {
            str(d.get("code"))
            for d in (report_blob.get("diagnostics") or ())
            if isinstance(d, dict)
        }
        missing = [c for c in expected.diagnostic_codes if c not in codes]
        if missing:
            errors.append(f"missing diagnostic codes: {missing}")
    for asset, expected_rows in dict(expected.sink_assets).items():
        actual_rows = _rows_as_dicts(list(rt.memory.get(asset) or ()))
        expected_dicts = [dict(r) for r in expected_rows]
        if actual_rows != expected_dicts:
            errors.append(
                f"sink asset {asset!r} mismatch: {actual_rows!r} != {expected_dicts!r}"
            )

    if identity is not None:
        report_blob = {
            **report_blob,
            "metadata": {
                **dict(report_blob.get("metadata") or {}),
                "fake_run_id": identity.run_id,
            },
        }

    return PipelineCaseResult(
        case_id=case.case_id,
        status=status,
        plan=plan_blob,
        report=report_blob,
        ok=not errors,
        errors=tuple(errors),
    )


def assert_case_succeeded(result: PipelineCaseResult) -> None:
    """Pytest helper: require ``result.ok`` and succeeded status."""
    if not result.ok:
        raise AssertionError(
            f"Pipeline case {result.case_id!r} failed: {list(result.errors)}"
        )
    if result.status != RunStatus.SUCCEEDED.value and result.status != "succeeded":
        raise AssertionError(
            f"Pipeline case {result.case_id!r} status was {result.status!r}"
        )


def emit_case_result_json(
    result: PipelineCaseResult,
    path: str | Path,
) -> None:
    """Write a case result JSON document (secret-free normalized plan/report)."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = result.to_dict()
    _assert_no_resolved_secrets(payload, path="case_result")
    target.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def inject_faults(*specs: FaultSpec):
    """Case-level fault binding (preview alias of ``with_faults``)."""
    return with_faults(*specs)


__all__ = [
    "ExpectedResult",
    "FakeClock",
    "FakeRunIdentity",
    "FakeSecretProvider",
    "PipelineCaseResult",
    "PipelineTestCase",
    "assert_case_succeeded",
    "assert_snapshots_match",
    "emit_case_result_json",
    "inject_faults",
    "run_pipeline_case",
    "snapshot_plan",
    "snapshot_report",
]
