# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnnecessaryIsInstance=false
"""Public behavioral provider conformance, never execution qualification.

Callbacks compare synthetic outputs and effects in process. Reports deliberately
exclude providers, plans, rows, exceptions and callback serialization hooks.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any, Literal

import anyio
from anyio.lowlevel import checkpoint

from etlantic.authoring.definition import PipelineDefinition
from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.pipeline import Pipeline
from etlantic.plan import (
    plan_from_json,
    plan_pipeline,
    plan_to_json,
    verify_plan_fingerprint,
)
from etlantic.profile import Profile
from etlantic.registry import PlanningContext
from etlantic.runtime.request import RunRequest
from etlantic.runtime.scheduler import LocalScheduler
from etlantic.validation import validate_pipeline

_CASE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_FAMILIES = json.loads(
    files("etlantic.schemas").joinpath("diagnostic-stability-tiers.json").read_text()
)["families"]
_CODE = re.compile(
    "(?:"
    + "|".join(
        re.escape(family) for family in sorted(_FAMILIES) if family.startswith("PM")
    )
    + r")[0-9]{3}\Z"
)


@dataclass(frozen=True, slots=True)
class AdaptiveConformanceCase:
    """One isolated public pipeline/profile/request and required effect oracle.

    ``verify(runtime, plan, report)`` must assert the relevant behavior or return
    a boolean. It may be async. ``report`` is None for planning/rejected cases.
    An explicit workspace enables source snapshots; the default writes no files.
    Malformed catalogues reject before invoking any factory.
    """

    case_id: str
    pipeline: type[Pipeline] | PipelineDefinition
    profile: Profile
    request: RunRequest
    runtime_factory: Callable[[], PipelineRuntime]
    verify: Callable[[PipelineRuntime, Any, Any], Any]
    mode: Literal["planning", "execution"] = "execution"
    expected_acceptance: bool = True
    expected_code: str | None = None
    context_factory: Callable[[PipelineRuntime, Profile], PlanningContext] | None = None
    workspace: str | Path | None = None


@dataclass(frozen=True, slots=True)
class _CaseResult:
    case_id: str
    mode: str
    expected_acceptance: bool
    observed_acceptance: bool
    passed: bool
    code: str | None
    fingerprint: str | None

    def __post_init__(self) -> None:
        if (
            type(self.case_id) is not str
            or not _CASE_ID.fullmatch(self.case_id)
            or type(self.mode) is not str
            or self.mode not in {"planning", "execution"}
            or any(
                type(value) is not bool
                for value in (
                    self.expected_acceptance,
                    self.observed_acceptance,
                    self.passed,
                )
            )
            or (
                self.code is not None
                and (type(self.code) is not str or not _CODE.fullmatch(self.code))
            )
            or (
                self.fingerprint is not None
                and (
                    type(self.fingerprint) is not str
                    or not re.fullmatch(r"(?:sha256:)?[0-9a-f]{64}", self.fingerprint)
                )
            )
        ):
            raise ValueError("Invalid adaptive conformance result")

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "mode": self.mode,
            "expected_acceptance": self.expected_acceptance,
            "observed_acceptance": self.observed_acceptance,
            "passed": self.passed,
            "code": self.code,
            "fingerprint": self.fingerprint,
        }


@dataclass(frozen=True, slots=True)
class AdaptiveConformanceReport:
    """Non-authoritative canonical results, containing trusted primitives only."""

    results: tuple[_CaseResult, ...]

    def __post_init__(self) -> None:
        results = tuple(self.results)
        if not 0 < len(results) <= 256 or any(
            type(result) is not _CaseResult for result in results
        ):
            raise ValueError("Invalid adaptive conformance report")
        if len({result.case_id for result in results}) != len(results):
            raise ValueError("Duplicate adaptive conformance result")
        object.__setattr__(
            self, "results", tuple(sorted(results, key=lambda r: r.case_id))
        )

    @property
    def passed(self) -> bool:
        return all(result.passed for result in self.results)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "etlantic.adaptive_provider_conformance/1",
            "passed": self.passed,
            "results": [result.to_dict() for result in self.results],
        }


def _catalogue(
    cases: Iterable[AdaptiveConformanceCase],
) -> tuple[AdaptiveConformanceCase, ...]:
    # Bound iterable consumption as well as the eventual retained report.
    catalogue = []
    try:
        for case in cases:
            if len(catalogue) == 256:
                raise ValueError("Adaptive conformance catalogue exceeds 256 cases")
            catalogue.append(case)
    except (TypeError, RuntimeError):
        raise ValueError("Invalid adaptive conformance catalogue") from None
    identifiers = set()
    for case in catalogue:
        if type(case) is not AdaptiveConformanceCase:
            raise ValueError("Invalid adaptive conformance case")
        pipeline_ok = isinstance(case.pipeline, PipelineDefinition) or (
            isinstance(case.pipeline, type) and issubclass(case.pipeline, Pipeline)
        )
        if (
            type(case.case_id) is not str
            or not _CASE_ID.fullmatch(case.case_id)
            or case.case_id in identifiers
            or not pipeline_ok
            or not isinstance(case.profile, Profile)
            or not isinstance(case.request, RunRequest)
            or case.mode not in {"planning", "execution"}
            or type(case.expected_acceptance) is not bool
            or not callable(case.runtime_factory)
            or not callable(case.verify)
            or (case.context_factory is not None and not callable(case.context_factory))
            or (case.expected_acceptance and case.expected_code is not None)
            or (
                not case.expected_acceptance
                and (
                    type(case.expected_code) is not str
                    or not _CODE.fullmatch(case.expected_code)
                )
            )
            or (
                case.workspace is not None
                and not isinstance(case.workspace, (str, Path))
            )
        ):
            raise ValueError("Invalid adaptive conformance case")
        identifiers.add(case.case_id)
    if not catalogue:
        raise ValueError("Adaptive conformance requires at least one case")
    return tuple(sorted(catalogue, key=lambda case: case.case_id))


def _known_code(error: Exception) -> str | None:
    # Do not call provider exception serializers or stringify their payloads.
    from etlantic.exceptions import PipelineExecutionError, PipelineValidationError

    if isinstance(error, PipelineExecutionError):
        code = error.code
    elif isinstance(error, PipelineValidationError):
        diagnostics = error.report.diagnostics
        code = next((d.code for d in diagnostics if str(d.severity) == "error"), None)
    else:
        return None
    return code if type(code) is str and _CODE.fullmatch(code) else None


async def arun_adaptive_provider_conformance_suite(
    cases: Iterable[AdaptiveConformanceCase],
) -> AdaptiveConformanceReport:
    """Exercise stored public plans and scheduler; cancellation drains/propagates.

    Expected rejection must have the exact known PMADP code and pass the effect
    oracle. Unrecognized exceptions are behavioral failures, never success proof.
    Passing does not mutate packaged support, allowlists or graduation records.
    """
    catalogue = _catalogue(cases)
    results = []
    runtimes = []
    for case in catalogue:
        await checkpoint()
        try:
            runtime = case.runtime_factory()
            if not isinstance(runtime, PipelineRuntime) or any(
                runtime is rt for rt in runtimes
            ):
                raise ValueError(
                    "Runtime factory must return an isolated PipelineRuntime"
                )
            runtimes.append(runtime)
            context = (
                case.context_factory(runtime, case.profile)
                if case.context_factory
                else PlanningContext.create(case.profile, registry=runtime.registry)
            )
            if (
                not isinstance(context, PlanningContext)
                or context.profile != case.profile
            ):
                raise ValueError("Invalid conformance planning context")
        except Exception:
            raise ValueError("Invalid adaptive conformance factory/context") from None
        plan = report = None
        accepted = False
        code = fingerprint = None
        behavioral_error = False
        try:
            validation = validate_pipeline(
                case.pipeline,
                context=context,
                profile=case.profile,
                parameter_overrides=case.request.parameter_overrides,
            )
            validation.raise_for_errors()
            plan = plan_pipeline(
                case.pipeline,
                context=context,
                profile=case.profile,
                request=case.request,
            )
            plan = plan_from_json(plan_to_json(plan))
            verify_plan_fingerprint(plan)
            fingerprint = plan.fingerprint
            if case.mode == "execution":
                try:
                    report = await LocalScheduler().execute(
                        plan,
                        request=case.request,
                        runtime=runtime,
                        workspace=case.workspace,
                    )
                finally:
                    # Scheduler cancellation becomes an ordinary pipeline error
                    # after draining. AnyIO scopes redeliver at a checkpoint;
                    # asyncio Task.cancel() needs its outstanding request checked
                    # explicitly because it is delivered only once.
                    await checkpoint()
                    try:
                        task = asyncio.current_task()
                    except RuntimeError:  # Non-asyncio AnyIO backend.
                        task = None
                    if task is not None and task.cancelling():
                        raise asyncio.CancelledError
                accepted = report.status.value == "succeeded"
                if not accepted:
                    code = next(
                        (
                            d.code
                            for d in report.diagnostics
                            if type(d.code) is str and _CODE.fullmatch(d.code)
                        ),
                        None,
                    )
                    behavioral_error = code is None
            else:
                accepted = True
        except Exception as error:
            code = _known_code(error)
            behavioral_error = code is None
        oracle_passed = False
        try:
            verified = case.verify(runtime, plan, report)
            if inspect.isawaitable(verified):
                verified = await verified
            if verified is not None and type(verified) is not bool:
                raise ValueError("Adaptive conformance oracle must return bool or None")
            oracle_passed = verified is not False
        except AssertionError:
            oracle_passed = False
        except Exception:
            raise ValueError("Invalid adaptive conformance oracle") from None
        passed = (
            not behavioral_error
            and accepted == case.expected_acceptance
            and code == case.expected_code
            and oracle_passed
        )
        results.append(
            _CaseResult(
                case.case_id,
                case.mode,
                case.expected_acceptance,
                accepted,
                passed,
                code,
                fingerprint,
            )
        )
    await checkpoint()
    return AdaptiveConformanceReport(tuple(results))


def run_adaptive_provider_conformance_suite(
    cases: Iterable[AdaptiveConformanceCase],
) -> AdaptiveConformanceReport:
    """Synchronous counterpart; use the async helper inside an event loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise RuntimeError(
            "Use arun_adaptive_provider_conformance_suite in an async loop"
        )
    return anyio.run(arun_adaptive_provider_conformance_suite, cases)


__all__ = [
    "AdaptiveConformanceCase",
    "AdaptiveConformanceReport",
    "arun_adaptive_provider_conformance_suite",
    "run_adaptive_provider_conformance_suite",
]
