"""Map SparkForge debug / run modes onto ETLantic RunRequest surfaces."""

from __future__ import annotations

from typing import Any

from etlantic.runtime.execute import DebugSession
from etlantic.runtime.request import (
    MaterializationPolicy,
    RetryPolicy,
    RunIntent,
    RunRequest,
    RunSelection,
)
from medallantic.compat import retry_policy_from_sparkforge

_INTENT_MAP: dict[str, RunIntent] = {
    "standard": RunIntent.STANDARD,
    "initial": RunIntent.INITIALIZE,
    "initial_load": RunIntent.INITIALIZE,
    "initialize": RunIntent.INITIALIZE,
    "incremental": RunIntent.INCREMENTAL,
    "full_refresh": RunIntent.REFRESH,
    "refresh": RunIntent.REFRESH,
    "validation": RunIntent.VALIDATE,
    "validation_only": RunIntent.VALIDATE,
    "validate": RunIntent.VALIDATE,
    "backfill": RunIntent.BACKFILL,
    "replay": RunIntent.REPLAY,
}


def intent_from_sparkforge(mode: str | None) -> RunIntent:
    """Map SparkForge run-mode strings to RunIntent."""
    key = (mode or "standard").strip().lower()
    if key not in _INTENT_MAP:
        raise ValueError(f"Unsupported SparkForge run mode: {mode!r}")
    return _INTENT_MAP[key]


def selection_from_sparkforge(
    *,
    run_until: str | None = None,
    run_one: str | None = None,
    run_from: str | None = None,
) -> RunSelection:
    """Map SparkForge selective-execution flags to RunSelection."""
    selected = [x for x in (run_until, run_one, run_from) if x]
    if len(selected) > 1:
        raise ValueError("Use only one of run_until, run_one, or run_from")
    if run_until:
        return RunSelection.until(run_until)
    if run_one:
        return RunSelection.only(run_one)
    if run_from:
        return RunSelection.from_(run_from)
    return RunSelection.all()


def debug_request_from_sparkforge(
    *,
    mode: str | None = "standard",
    run_until: str | None = None,
    run_one: str | None = None,
    run_from: str | None = None,
    skip_writes: bool = False,
    materialization: MaterializationPolicy | None = None,
    retry: dict[str, Any] | RetryPolicy | None = None,
    parameter_overrides: dict[str, dict[str, Any]] | None = None,
) -> RunRequest:
    """Build a RunRequest from SparkForge debug/session options.

    ``skip_writes`` sets ``no_write=True`` only. Materialization stays
    ``DEFAULT`` unless the caller passes ``materialization=`` explicitly.
    ``VALIDATE`` intent also sets ``no_write=True``.
    """
    intent = intent_from_sparkforge(mode)
    no_write = skip_writes or intent is RunIntent.VALIDATE
    retry_policy: RetryPolicy
    if isinstance(retry, RetryPolicy):
        retry_policy = retry
    elif isinstance(retry, dict):
        retry_policy = retry_policy_from_sparkforge(retry)
    else:
        retry_policy = RetryPolicy()
    return RunRequest(
        selection=selection_from_sparkforge(
            run_until=run_until, run_one=run_one, run_from=run_from
        ),
        intent=intent,
        materialization=materialization or MaterializationPolicy.DEFAULT,
        no_write=no_write,
        retry=retry_policy,
        parameter_overrides=dict(parameter_overrides or {}),
    )


def bind_debug_session(
    pipeline_cls: type[Any],
    *,
    profile: str | Any = "development",
) -> DebugSession:
    """Return an ETLantic DebugSession for an adapted pipeline class."""
    return DebugSession(pipeline_cls=pipeline_cls, profile=profile)
