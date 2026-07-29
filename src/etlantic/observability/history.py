"""Run history provider protocol (etlantic.run_history/1)."""

from __future__ import annotations

import json
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from etlantic.io_policy import SafeIoPolicy, read_text_safe, write_text_safe
from etlantic.reports.model import PipelineRunReport
from etlantic.runtime.events import (
    LifecycleEvent,
    RunHistoryRecord,
    SecurityEvent,
)

RUN_HISTORY_PROTOCOL = "etlantic.run_history/1"


@dataclass(frozen=True, slots=True)
class RunHistoryCapabilities:
    """Declared run-history provider capabilities."""

    durable: bool = True
    queryable: bool = True
    cross_process: bool = False
    event_stream: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "durable": self.durable,
            "queryable": self.queryable,
            "cross_process": self.cross_process,
            "event_stream": self.event_stream,
        }


@dataclass(frozen=True, slots=True)
class RunHistoryProviderDescriptor:
    """Installed run-history provider metadata."""

    name: str
    engine: str
    version: str = "0.34.0"
    protocol: str = RUN_HISTORY_PROTOCOL
    capabilities: RunHistoryCapabilities = field(default_factory=RunHistoryCapabilities)


@dataclass(frozen=True, slots=True)
class RunHistoryQuery:
    """Secret-free run history query filters."""

    pipeline_id: str | None = None
    status: str | None = None
    since: datetime | None = None
    until: datetime | None = None
    limit: int | None = None


@dataclass(frozen=True, slots=True)
class RunHistoryEntry:
    """Summary of one run in history."""

    run_id: str
    pipeline_id: str
    plan_id: str | None
    status: str
    started_at: datetime
    ended_at: datetime | None = None
    event_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "pipeline_id": self.pipeline_id,
            "plan_id": self.plan_id,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "event_count": self.event_count,
            "metadata": dict(self.metadata),
        }


@runtime_checkable
class RunHistoryProvider(Protocol):
    """Durable run-history provider protocol (/1)."""

    @property
    def descriptor(self) -> RunHistoryProviderDescriptor: ...

    def create_run(
        self,
        *,
        run_id: str,
        pipeline_id: str,
        plan_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None: ...

    def append_event(
        self,
        event: LifecycleEvent | SecurityEvent | RunHistoryRecord,
    ) -> None: ...

    def append_report(self, report: PipelineRunReport) -> None: ...

    def read_run(self, run_id: str) -> dict[str, Any] | None: ...

    def list_runs(self, query: RunHistoryQuery | None = None) -> list[RunHistoryEntry]: ...


@dataclass
class InMemoryRunHistoryProvider:
    """In-process run history for tests and conformance."""

    @property
    def descriptor(self) -> RunHistoryProviderDescriptor:
        return RunHistoryProviderDescriptor(
            name="memory",
            engine="memory",
            capabilities=RunHistoryCapabilities(
                durable=False,
                queryable=True,
                cross_process=False,
            ),
        )

    _runs: dict[str, dict[str, Any]] = field(default_factory=dict)
    _events: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    _reports: dict[str, dict[str, Any]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def create_run(
        self,
        *,
        run_id: str,
        pipeline_id: str,
        plan_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        with self._lock:
            self._runs[run_id] = {
                "run_id": run_id,
                "pipeline_id": pipeline_id,
                "plan_id": plan_id,
                "status": "running",
                "started_at": datetime.now(UTC).isoformat(),
                "metadata": dict(metadata or {}),
            }
            self._events.setdefault(run_id, [])

    def append_event(
        self,
        event: LifecycleEvent | SecurityEvent | RunHistoryRecord,
    ) -> None:
        payload = (
            event.to_dict()
            if hasattr(event, "to_dict")
            else dict(event)  # type: ignore[arg-type]
        )
        run_id = str(payload.get("run_id") or "")
        with self._lock:
            self._events.setdefault(run_id, []).append(payload)

    def append_report(self, report: PipelineRunReport) -> None:
        data = report.to_dict()
        with self._lock:
            self._reports[report.run_id] = data
            if report.run_id in self._runs:
                self._runs[report.run_id]["status"] = report.status.value
                self._runs[report.run_id]["ended_at"] = (
                    report.ended_at.isoformat() if report.ended_at else None
                )

    def read_run(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            if run_id not in self._runs and run_id not in self._reports:
                return None
            return {
                "run": dict(self._runs.get(run_id, {})),
                "events": list(self._events.get(run_id, [])),
                "report": dict(self._reports.get(run_id, {})),
            }

    def list_runs(self, query: RunHistoryQuery | None = None) -> list[RunHistoryEntry]:
        q = query or RunHistoryQuery()
        with self._lock:
            entries: list[RunHistoryEntry] = []
            for run_id, meta in self._runs.items():
                if q.pipeline_id and meta.get("pipeline_id") != q.pipeline_id:
                    continue
                status = str(meta.get("status") or "unknown")
                if q.status and status != q.status:
                    continue
                started_raw = meta.get("started_at")
                started = (
                    datetime.fromisoformat(started_raw)
                    if isinstance(started_raw, str)
                    else datetime.now(UTC)
                )
                if q.since and started < q.since:
                    continue
                if q.until and started > q.until:
                    continue
                ended_raw = meta.get("ended_at")
                ended = (
                    datetime.fromisoformat(ended_raw)
                    if isinstance(ended_raw, str)
                    else None
                )
                entries.append(
                    RunHistoryEntry(
                        run_id=run_id,
                        pipeline_id=str(meta.get("pipeline_id") or ""),
                        plan_id=meta.get("plan_id"),
                        status=status,
                        started_at=started,
                        ended_at=ended,
                        event_count=len(self._events.get(run_id, [])),
                        metadata=dict(meta.get("metadata") or {}),
                    )
                )
            entries.sort(key=lambda e: e.started_at, reverse=True)
            if q.limit is not None:
                entries = entries[: q.limit]
            return entries


@dataclass
class FileRunHistoryProvider:
    """Filesystem-backed run history (events JSONL + report JSON per run)."""

    root: Path
    policy: SafeIoPolicy | None = None
    _memory: InMemoryRunHistoryProvider = field(
        default_factory=InMemoryRunHistoryProvider
    )
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        self.root = Path(self.root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        if self.policy is None:
            self.policy = SafeIoPolicy.for_root(self.root)
        self._load_existing()

    @property
    def descriptor(self) -> RunHistoryProviderDescriptor:
        return RunHistoryProviderDescriptor(
            name="file",
            engine="file",
            capabilities=RunHistoryCapabilities(
                durable=True,
                queryable=True,
                cross_process=True,
            ),
        )

    def _run_dir(self, run_id: str) -> Path:
        return self.root / run_id

    def _load_existing(self) -> None:
        for path in sorted(self.root.iterdir()):
            if not path.is_dir():
                continue
            run_id = path.name
            meta_path = path / "meta.json"
            if meta_path.exists():
                try:
                    _resolved, text, _ = read_text_safe(
                        meta_path, self.policy, run_id="history-load"
                    )
                    meta = json.loads(text)
                    self._memory.create_run(
                        run_id=run_id,
                        pipeline_id=str(meta.get("pipeline_id") or ""),
                        plan_id=meta.get("plan_id"),
                        metadata=dict(meta.get("metadata") or {}),
                    )
                    self._memory._runs[run_id].update(meta)
                except Exception:
                    continue
            events_path = path / "events.jsonl"
            if events_path.exists():
                try:
                    _resolved, text, _ = read_text_safe(
                        events_path, self.policy, run_id="history-load"
                    )
                    for line in text.splitlines():
                        if not line.strip():
                            continue
                        payload = json.loads(line)
                        self._memory._events.setdefault(run_id, []).append(payload)
                except Exception:
                    continue
            report_path = path / "report.json"
            if report_path.exists():
                try:
                    _resolved, text, _ = read_text_safe(
                        report_path, self.policy, run_id="history-load"
                    )
                    self._memory._reports[run_id] = json.loads(text)
                except Exception:
                    continue

    def create_run(
        self,
        *,
        run_id: str,
        pipeline_id: str,
        plan_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        assert self.policy is not None
        with self._lock:
            self._memory.create_run(
                run_id=run_id,
                pipeline_id=pipeline_id,
                plan_id=plan_id,
                metadata=metadata,
            )
            run_dir = self._run_dir(run_id)
            run_dir.mkdir(parents=True, exist_ok=True)
            meta = {
                "run_id": run_id,
                "pipeline_id": pipeline_id,
                "plan_id": plan_id,
                "status": "running",
                "started_at": datetime.now(UTC).isoformat(),
                "metadata": dict(metadata or {}),
            }
            write_text_safe(
                run_dir / "meta.json",
                json.dumps(meta, sort_keys=True, indent=2),
                self.policy,
                run_id=run_id,
            )

    def append_event(
        self,
        event: LifecycleEvent | SecurityEvent | RunHistoryRecord,
    ) -> None:
        assert self.policy is not None
        payload = event.to_dict()
        run_id = str(payload.get("run_id") or "")
        with self._lock:
            self._memory.append_event(event)
            run_dir = self._run_dir(run_id)
            run_dir.mkdir(parents=True, exist_ok=True)
            events_path = run_dir / "events.jsonl"
            existing = ""
            if events_path.exists():
                _resolved, existing, _ = read_text_safe(
                    events_path, self.policy, run_id=run_id
                )
            write_text_safe(
                events_path,
                existing + json.dumps(payload, sort_keys=True) + "\n",
                self.policy,
                run_id=run_id,
            )

    def append_report(self, report: PipelineRunReport) -> None:
        assert self.policy is not None
        with self._lock:
            self._memory.append_report(report)
            run_dir = self._run_dir(report.run_id)
            run_dir.mkdir(parents=True, exist_ok=True)
            write_text_safe(
                run_dir / "report.json",
                report.to_json(),
                self.policy,
                run_id=report.run_id,
            )
            meta_path = run_dir / "meta.json"
            meta = dict(self._memory._runs.get(report.run_id, {}))
            meta["status"] = report.status.value
            meta["ended_at"] = (
                report.ended_at.isoformat() if report.ended_at else None
            )
            write_text_safe(
                meta_path,
                json.dumps(meta, sort_keys=True, indent=2),
                self.policy,
                run_id=report.run_id,
            )

    def read_run(self, run_id: str) -> dict[str, Any] | None:
        return self._memory.read_run(run_id)

    def list_runs(self, query: RunHistoryQuery | None = None) -> list[RunHistoryEntry]:
        return self._memory.list_runs(query)
