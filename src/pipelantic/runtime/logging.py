"""Structured logging with secret redaction."""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from pipelantic.secrets.value import SecretValue

_SECRET_KEY_RE = re.compile(
    r"(password|secret|token|api[_-]?key|credential|authorization)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class LogRecord:
    """Structured log record (secret-free)."""

    level: str
    message: str
    at: datetime = field(default_factory=lambda: datetime.now(UTC))
    run_id: str | None = None
    pipeline_id: str | None = None
    step_name: str | None = None
    attempt: int | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["at"] = self.at.isoformat()
        return data


def redact_value(value: Any) -> Any:
    """Recursively redact secrets and sensitive keys."""
    if isinstance(value, SecretValue):
        return "***"
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if _SECRET_KEY_RE.search(str(key)):
                out[str(key)] = "***"
            else:
                out[str(key)] = redact_value(item)
        return out
    if isinstance(value, (list, tuple)):
        return [redact_value(v) for v in value]
    return value


class RunLogger:
    """Contextual logger that redacts secrets before emission."""

    def __init__(
        self,
        *,
        run_id: str,
        pipeline_id: str,
        logger: logging.Logger | None = None,
    ) -> None:
        self.run_id = run_id
        self.pipeline_id = pipeline_id
        self._logger = logger or logging.getLogger("pipelantic.runtime")
        self.records: list[LogRecord] = []

    def log(
        self,
        level: str,
        message: str,
        *,
        step_name: str | None = None,
        attempt: int | None = None,
        **extras: Any,
    ) -> LogRecord:
        record = LogRecord(
            level=level,
            message=message,
            run_id=self.run_id,
            pipeline_id=self.pipeline_id,
            step_name=step_name,
            attempt=attempt,
            extras=redact_value(extras),
        )
        self.records.append(record)
        getattr(self._logger, level.lower(), self._logger.info)(
            "%s run=%s step=%s %s",
            message,
            self.run_id,
            step_name,
            redact_value(extras),
        )
        return record
