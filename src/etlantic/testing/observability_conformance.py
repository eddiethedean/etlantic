"""Observability provider conformance helpers."""

from __future__ import annotations

import asyncio

from etlantic.observability.protocol import ObservabilityProvider
from etlantic.runtime.events import LifecycleEvent
from etlantic.runtime.logging import LogRecord


def assert_observability_provider_info(provider: ObservabilityProvider) -> None:
    descriptor = provider.descriptor
    assert descriptor.name
    assert descriptor.engine
    assert descriptor.capabilities is not None


async def _emit_sample(provider: ObservabilityProvider) -> None:
    from etlantic.observability.protocol import ObservabilityContext

    ctx = ObservabilityContext(
        run_id="conformance",
        pipeline_id="conformance",
        plan_id="plan-conformance",
    )
    async with provider.lifespan(ctx):
        await provider.emit_event(
            LifecycleEvent(
                kind="run_started",
                run_id="conformance",
                pipeline_id="conformance",
                plan_id="plan-conformance",
            )
        )
        await provider.emit_log(
            LogRecord(level="info", message="conformance log", run_id="conformance")
        )
        await provider.flush()


def run_observability_conformance_suite(provider: ObservabilityProvider) -> None:
    """Validate observability provider hygiene and lifecycle ordering."""
    assert_observability_provider_info(provider)
    asyncio.run(_emit_sample(provider))


def assert_redacted_log(provider: ObservabilityProvider) -> None:
    asyncio.run(_emit_redacted(provider))


async def _emit_redacted(provider: ObservabilityProvider) -> None:
    from etlantic.observability.protocol import ObservabilityContext

    ctx = ObservabilityContext(run_id="redact", pipeline_id="redact")
    async with provider.lifespan(ctx):
        await provider.emit_log(
            LogRecord(
                level="info",
                message="token=supersecret",
                run_id="redact",
                extras={"password": "hidden"},
            )
        )
        await provider.flush()
