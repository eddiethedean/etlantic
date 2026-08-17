"""Experimental Kafka reference connector (fake by default)."""

from __future__ import annotations

__version__ = "0.46.0"

from etlantic_kafka.connectors import (
    KafkaSinkConnector,
    KafkaSourceConnector,
    create_sink,
    create_source,
)
from etlantic_kafka.fake import FakeKafka, live_bootstrap

__all__ = [
    "FakeKafka",
    "KafkaSinkConnector",
    "KafkaSourceConnector",
    "__version__",
    "create_sink",
    "create_source",
    "live_bootstrap",
]
