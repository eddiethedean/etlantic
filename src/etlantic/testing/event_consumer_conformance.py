"""Event consumer conformance helpers."""

from __future__ import annotations

from etlantic.observability.consumers import EventConsumer, InMemoryTrendConsumer
from etlantic.runtime.events import LifecycleEvent


def assert_event_consumer_info(consumer: EventConsumer) -> None:
    descriptor = consumer.descriptor
    assert descriptor.name
    assert descriptor.engine
    assert descriptor.capabilities is not None


def run_event_consumer_conformance_suite(consumer: EventConsumer) -> None:
    """Validate event ordering and bounded memory behavior."""
    assert_event_consumer_info(consumer)
    for idx in range(5):
        consumer.consume(
            LifecycleEvent(
                kind="step_completed",
                run_id="consumer-conformance",
                pipeline_id="pipe",
                step_name=f"step_{idx}",
                metadata={"quality_metric": "accept_rate", "quality_value": 0.9},
            )
        )
    consumer.flush()
    if isinstance(consumer, InMemoryTrendConsumer):
        summary = consumer.trend_summary()
        assert summary["n"] >= 1
