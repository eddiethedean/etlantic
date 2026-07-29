"""Bridge EventBus emissions to observability providers and event consumers."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from etlantic.observability.consumers import EventConsumer
from etlantic.observability.history import RunHistoryProvider
from etlantic.observability.protocol import ObservabilityContext, ObservabilityProvider
from etlantic.profile import Profile
from etlantic.reports.model import PipelineRunReport
from etlantic.runtime.events import EventBus, LifecycleEvent, SecurityEvent
from etlantic.runtime.logging import LogRecord, redact_message, redact_value

_LOG = logging.getLogger(__name__)


def _redact_event(
    event: LifecycleEvent | SecurityEvent,
) -> LifecycleEvent | SecurityEvent:
    if isinstance(event, LifecycleEvent):
        return LifecycleEvent(
            kind=event.kind,
            run_id=event.run_id,
            pipeline_id=event.pipeline_id,
            at=event.at,
            step_name=event.step_name,
            attempt=event.attempt,
            status=event.status,
            message=redact_message(event.message) if event.message else None,
            plan_id=event.plan_id,
            region_id=event.region_id,
            physical_unit=event.physical_unit,
            backend=event.backend,
            correlation_id=event.correlation_id,
            annotations=redact_value(dict(event.annotations)),
            metadata=redact_value(dict(event.metadata)),
            schema_version=event.schema_version,
        )
    return SecurityEvent(
        kind=event.kind,
        run_id=event.run_id,
        provider=event.provider,
        secret_identity=event.secret_identity,
        outcome=event.outcome,
        at=event.at,
        step_name=event.step_name,
        message=redact_message(event.message) if event.message else None,
        schema_version=event.schema_version,
        subject=event.subject,
        plan_id=event.plan_id,
        correlation_id=event.correlation_id,
        metadata=redact_value(dict(event.metadata)),
    )


@dataclass
class ObservabilityBridge:
    """Fan-out lifecycle events to observability providers and consumers."""

    events: EventBus
    profile: Profile | None = None
    observability_providers: dict[str, ObservabilityProvider] = field(
        default_factory=dict
    )
    run_history_providers: dict[str, RunHistoryProvider] = field(default_factory=dict)
    event_consumers: dict[str, EventConsumer] = field(default_factory=dict)
    _active_history: RunHistoryProvider | None = field(default=None, repr=False)
    _provider_errors: list[str] = field(default_factory=list, repr=False)
    _event_count: int = field(default=0, repr=False)
    _pending_events: list[LifecycleEvent | SecurityEvent] = field(
        default_factory=list, repr=False
    )
    _pending_logs: list[LogRecord] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        self.events.subscribe(self._on_event)

    def configure_for_profile(self, profile: Profile) -> None:
        self.profile = profile
        history_id = profile.run_history_provider
        if history_id and history_id in self.run_history_providers:
            self._active_history = self.run_history_providers[history_id]

    def start_run(
        self,
        *,
        run_id: str,
        pipeline_id: str,
        plan_id: str | None,
        correlation_id: str | None = None,
    ) -> None:
        if self._active_history is None:
            return
        self._active_history.create_run(
            run_id=run_id,
            pipeline_id=pipeline_id,
            plan_id=plan_id,
            metadata={"correlation_id": correlation_id},
        )

    def _on_event(self, event: LifecycleEvent | SecurityEvent) -> None:
        safe = _redact_event(event)
        self._event_count += 1
        self._pending_events.append(safe)
        for consumer in self.event_consumers.values():
            try:
                consumer.consume(safe)
            except Exception as exc:
                msg = redact_message(str(exc))
                _LOG.warning("Event consumer failed: %s", msg)
                self._provider_errors.append(msg)
                if (
                    self.profile
                    and self.profile.observability_delivery == "durable_audit"
                ):
                    raise RuntimeError(
                        "Event consumer failed under durable_audit"
                    ) from exc
        if self._active_history is not None:
            try:
                self._active_history.append_event(safe)
            except Exception as exc:
                msg = redact_message(str(exc))
                _LOG.warning("Run history append failed: %s", msg)
                self._provider_errors.append(msg)
                if (
                    self.profile
                    and self.profile.observability_delivery == "durable_audit"
                ):
                    raise RuntimeError(
                        "Run history event persistence failed under durable_audit"
                    ) from exc

    def emit_log(self, record: LogRecord) -> None:
        safe = LogRecord(
            level=record.level,
            message=redact_message(record.message),
            at=record.at,
            run_id=record.run_id,
            pipeline_id=record.pipeline_id,
            step_name=record.step_name,
            attempt=record.attempt,
            extras=redact_value(dict(record.extras)),
        )
        if len(self._pending_logs) >= 10_000:
            self._pending_logs.pop(0)
        self._pending_logs.append(safe)

    def persist_report(self, report: PipelineRunReport) -> None:
        if self._active_history is not None:
            try:
                self._active_history.append_report(report)
            except Exception as exc:
                msg = redact_message(str(exc))
                _LOG.warning("Run history report append failed: %s", msg)
                self._provider_errors.append(msg)
                if (
                    self.profile
                    and self.profile.observability_delivery == "durable_audit"
                ):
                    raise RuntimeError(
                        "Run history report persistence failed under durable_audit"
                    ) from exc

    async def aflush(self) -> None:
        errors: list[str] = []
        for consumer in self.event_consumers.values():
            try:
                consumer.flush()
            except Exception as exc:
                errors.append(redact_message(str(exc)))
        if self.observability_providers:
            try:
                await self._dispatch_pending()
            except Exception as exc:
                errors.append(redact_message(str(exc)))
        if errors:
            self._provider_errors.extend(errors)
            if self.profile and self.profile.observability_delivery == "durable_audit":
                raise RuntimeError(
                    "Observability flush failed under durable_audit: "
                    + "; ".join(errors)
                )
        self._pending_events.clear()
        self._pending_logs.clear()

    async def _dispatch_pending(self) -> None:
        for provider in self.observability_providers.values():
            ctx = ObservabilityContext(run_id="flush", pipeline_id="")
            async with provider.lifespan(ctx):
                for event in self._pending_events:
                    await provider.emit_event(event)
                for record in self._pending_logs:
                    await provider.emit_log(record)
                await provider.flush()

    def flush(self) -> None:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self.aflush())
        else:
            raise RuntimeError(
                "ObservabilityBridge.flush() cannot run inside an active event loop; "
                "await aflush() instead."
            )

    def observability_metadata(self) -> dict[str, Any]:
        return {
            "event_count": self._event_count,
            "provider_ids": sorted(self.observability_providers.keys()),
            "history_provider": (
                self.profile.run_history_provider if self.profile else None
            ),
            "delivery": (
                self.profile.observability_delivery if self.profile else "best_effort"
            ),
            "provider_errors": list(self._provider_errors),
        }
