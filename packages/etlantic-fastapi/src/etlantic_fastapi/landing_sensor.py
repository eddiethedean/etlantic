"""Landing-zone directory watch submitter (039-L) — outside ETLantic core.

Continuous directory watching is a **submitter**, not a third ``Extract`` kind.
This module lives in ``etlantic-fastapi`` (or examples) and must never move under
``src/etlantic/``. Watchers call the durable submit API with workspace-scoped
``local-files`` binding refs and must **never** embed file contents in plan or
submit bodies.
"""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Callable, Mapping, MutableMapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LANDING_BINDING_REF_SCHEMA = "etlantic.control_plane.landing_binding_ref/1"

SubmitRun = Callable[[str, Mapping[str, Any], str], Mapping[str, Any]]
"""``(definition_id, payload, idempotency_key) -> accept receipt mapping``."""


def local_files_binding_ref(
    *,
    root_ref: str = "landing",
    root: str = "inbox",
    glob: str = "*.csv",
    mode: str = "snapshot",
    provider: str = "local-files",
    format: str = "csv",
) -> dict[str, Any]:
    """0.38 ``local-files``-style binding reference (paths/refs only, no bytes)."""
    return {
        "schema": LANDING_BINDING_REF_SCHEMA,
        "provider": provider,
        "format": format,
        "root_ref": root_ref,
        "root": root,
        "glob": glob,
        "mode": mode,
    }


def file_identity_ref(path: Path, *, watch_root: Path) -> dict[str, Any]:
    """Stable relative identity for a dropped file (never contents)."""
    try:
        relative = path.resolve().relative_to(watch_root.resolve()).as_posix()
    except ValueError:
        relative = path.name
    return {
        "name": path.name,
        "relative": relative,
        "suffix": path.suffix,
    }


def build_submit_payload(
    *,
    definition_id: str,
    binding_ref: Mapping[str, Any],
    file_ref: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Durable submit payload with landing binding refs only (no file bytes)."""
    payload: dict[str, Any] = {
        "definition_id": definition_id,
        "trigger": "landing_watch",
        "landing": dict(binding_ref),
    }
    if file_ref is not None:
        payload["file"] = dict(file_ref)
    return payload


def idempotency_key_for_file(
    *,
    tenant_id: str,
    workspace_id: str,
    definition_id: str,
    file_ref: Mapping[str, Any],
) -> str:
    """Deterministic scoped key so the same drop does not double-accept."""
    material = (
        f"{tenant_id}:{workspace_id}:{definition_id}:"
        f"{file_ref.get('relative') or file_ref.get('name')}"
    )
    digest = hashlib.sha256(material.encode()).hexdigest()[:24]
    return f"landing-{digest}"


def assert_no_file_bytes(document: Mapping[str, Any], *, forbidden: str) -> None:
    """Raise ``AssertionError`` if ``forbidden`` file contents appear in ``document``."""
    blob = repr(document)
    if forbidden and forbidden in blob:
        raise AssertionError(
            "landing submitter must not embed file contents in plans or submit bodies"
        )


@dataclass
class LandingWatchSubmitter:
    """Stdlib polling loop that submits durable runs for new files.

    Prefer this over optional ``watchdog`` so CP1 has zero extra deps.
    """

    watch_dir: Path
    definition_id: str
    submit_run: SubmitRun
    binding_ref: Mapping[str, Any] = field(default_factory=local_files_binding_ref)
    tenant_id: str = "default"
    workspace_id: str = "default"
    poll_interval: float = 0.25
    pattern: str = "*.csv"
    _seen: MutableMapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.watch_dir = Path(self.watch_dir)
        self.watch_dir.mkdir(parents=True, exist_ok=True)

    def discover(self) -> list[Path]:
        return sorted(p for p in self.watch_dir.glob(self.pattern) if p.is_file())

    def poll_once(self) -> list[Mapping[str, Any]]:
        """Submit for newly seen files; return accept receipts."""
        receipts: list[Mapping[str, Any]] = []
        for path in self.discover():
            key = str(path.resolve())
            mtime = path.stat().st_mtime
            prior = self._seen.get(key)
            if prior is not None and prior >= mtime:
                continue
            self._seen[key] = mtime
            file_ref = file_identity_ref(path, watch_root=self.watch_dir)
            payload = build_submit_payload(
                definition_id=self.definition_id,
                binding_ref=self.binding_ref,
                file_ref=file_ref,
            )
            idem = idempotency_key_for_file(
                tenant_id=self.tenant_id,
                workspace_id=self.workspace_id,
                definition_id=self.definition_id,
                file_ref=file_ref,
            )
            receipt = self.submit_run(self.definition_id, payload, idem)
            receipts.append(dict(receipt))
        return receipts

    def run_until(
        self,
        stop: threading.Event,
        *,
        max_submits: int | None = None,
    ) -> list[Mapping[str, Any]]:
        """Poll until ``stop`` is set or ``max_submits`` receipts collected."""
        collected: list[Mapping[str, Any]] = []
        while not stop.is_set():
            collected.extend(self.poll_once())
            if max_submits is not None and len(collected) >= max_submits:
                break
            stop.wait(self.poll_interval)
        return collected


def make_testclient_submit_run(
    client: Any,
    *,
    principal: str = "alice",
) -> SubmitRun:
    """Adapt a FastAPI ``TestClient`` into a :data:`SubmitRun` callable."""

    def _submit(
        definition_id: str,
        payload: Mapping[str, Any],
        idempotency_key: str,
    ) -> Mapping[str, Any]:
        resp = client.post(
            f"/v1/definitions/{definition_id}/runs",
            headers={
                "X-Principal": principal,
                "Idempotency-Key": idempotency_key,
            },
            json={"payload": dict(payload)},
        )
        if resp.status_code != 202:
            raise RuntimeError(
                f"expected 202 from durable submit, got {resp.status_code}: {resp.text}"
            )
        return dict(resp.json())

    return _submit


__all__ = [
    "LANDING_BINDING_REF_SCHEMA",
    "LandingWatchSubmitter",
    "SubmitRun",
    "assert_no_file_bytes",
    "build_submit_payload",
    "file_identity_ref",
    "idempotency_key_for_file",
    "local_files_binding_ref",
    "make_testclient_submit_run",
]
