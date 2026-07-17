"""Structured logging with secret redaction."""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from etlantic.secrets.value import SecretValue

_SECRET_KEY_RE = re.compile(
    r"(password|passwd|pwd|secret|token|api[_-]?key|credential|authorization|"
    r"aws[_-]?secret[_-]?access[_-]?key|private[_-]?key)",
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


_SECRET_INLINE_RE = re.compile(
    r"(?i)(password|passwd|pwd|secret|token|api[_-]?key|credential|authorization|"
    r"aws[_-]?secret[_-]?access[_-]?key|private[_-]?key)"
    r"""\s*[=:]\s*['\"]?[^\s'\",;]+"""
)
_BEARER_RE = re.compile(r"(?i)(authorization\s*[:=]\s*)?bearer\s+[A-Za-z0-9\-._~+/]+=*")
_JSON_SECRET_RE = re.compile(
    r'(?i)("(?:password|passwd|pwd|secret|token|api[_-]?key|credential|'
    r'authorization|aws[_-]?secret[_-]?access[_-]?key|private[_-]?key)"\s*:\s*)'
    r'"[^"]*"'
)
_DSN_RE = re.compile(
    r"(?i)((?:postgres(?:ql)?|mysql|mariadb|mssql|oracle|sqlite|mongodb|"
    r"redis|rediss|amqp|amqps|couchdb|cassandra|https?)"
    r"(?:\+\w+)?://)([^:@/\s]*):([^@/\s]+)@"
)
# Generic userinfo credentials for any scheme (http basic-auth, custom DSNs).
_URL_USERINFO_RE = re.compile(r"(?i)([a-z][a-z0-9+.-]*://)([^:@/\s]+):([^@/\s]+)@")


def redact_message(message: str) -> str:
    """Redact likely secret assignments and DSN credentials from free-form text."""
    if not message:
        return message
    redacted = _BEARER_RE.sub("Bearer ***", message)
    redacted = _JSON_SECRET_RE.sub(r'\1"***"', redacted)
    redacted = _SECRET_INLINE_RE.sub(r"\1=***", redacted)
    redacted = _DSN_RE.sub(r"\1\2:***@", redacted)
    redacted = _URL_USERINFO_RE.sub(r"\1\2:***@", redacted)
    return redacted


def redact_value(value: Any) -> Any:
    """Recursively redact secrets, sensitive keys, and secret-like strings."""
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
    if isinstance(value, str):
        return redact_message(value)
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
        self._logger = logger or logging.getLogger("etlantic.runtime")
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
        safe_message = redact_message(str(message))
        record = LogRecord(
            level=level,
            message=safe_message,
            run_id=self.run_id,
            pipeline_id=self.pipeline_id,
            step_name=step_name,
            attempt=attempt,
            extras=redact_value(extras),
        )
        self.records.append(record)
        getattr(self._logger, level.lower(), self._logger.info)(
            "%s run=%s step=%s %s",
            safe_message,
            self.run_id,
            step_name,
            redact_value(extras),
        )
        return record
