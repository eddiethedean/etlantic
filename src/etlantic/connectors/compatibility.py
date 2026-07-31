"""Compatibility adapter for existing StorageBinding implementations."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Any

from etlantic.connectors.errors import ConnectorCompatibilityError
from etlantic.connectors.maturity import ConnectorMaturity
from etlantic.connectors.models import (
    STORAGE_PROTOCOL,
    CleanupReceipt,
    CommitReceipt,
    ConnectorInfo,
    ReconciliationResult,
    SchemaInspection,
    SinkPlan,
    WriteSession,
)
from etlantic.storage.protocol import StorageBinding


class StorageBindingAdapter:
    """Wrap a legacy :class:`~etlantic.storage.protocol.StorageBinding`.

    Does **not** claim connector capabilities. Provides a minimal sink-session
    surface that emits :class:`~etlantic.connectors.models.CommitReceipt` for
    publication-barrier coordination.
    """

    def __init__(self, binding: StorageBinding, *, provider: str | None = None) -> None:
        self._binding = binding
        self._provider = provider or getattr(binding, "name", "storage")
        self._sessions: dict[str, dict[str, Any]] = {}

    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name=str(self._provider),
            protocol=STORAGE_PROTOCOL,
            version="0.0.0",
            provider=str(self._provider),
            capabilities=(),
            maturity=ConnectorMaturity.EXPERIMENTAL,
            metadata={"adapter": "StorageBindingAdapter", "connector_claims": False},
        )

    async def plan_write(
        self,
        *,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> SinkPlan:
        return SinkPlan(
            provider=str(self._provider),
            protocol=STORAGE_PROTOCOL,
            write_mode=str(
                binding.get("mode") or context.get("write_mode") or "overwrite"
            ),
            required_capabilities=(),
            metadata={"adapter": True},
        )

    async def begin_write(
        self,
        *,
        plan: SinkPlan,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> WriteSession:
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = {
            "plan": plan,
            "binding": dict(binding),
            "batches": [],
            "prepared": False,
            "context": dict(context),
        }
        return WriteSession(
            session_id=session_id,
            provider=str(self._provider),
            protocol=STORAGE_PROTOCOL,
            metadata={"adapter": True},
        )

    async def write_batch(
        self,
        session: WriteSession,
        batch: Any,
        *,
        context: Mapping[str, Any],
    ) -> None:
        state = self._require_session(session)
        state["batches"].append(batch)
        state["context"].update(dict(context))

    async def prepare(
        self,
        session: WriteSession,
        *,
        context: Mapping[str, Any],
    ) -> None:
        state = self._require_session(session)
        state["prepared"] = True
        state["context"].update(dict(context))

    async def commit(
        self,
        session: WriteSession,
        *,
        context: Mapping[str, Any],
    ) -> CommitReceipt:
        state = self._require_session(session)
        ctx = {**state["context"], **dict(context)}
        binding = state["binding"]
        batches = state["batches"]
        data: Any
        if not batches:
            data = []
        elif len(batches) == 1:
            data = batches[0]
        else:
            merged: list[Any] = []
            for batch in batches:
                if isinstance(batch, list):
                    merged.extend(batch)
                else:
                    merged.append(batch)
            data = merged
        try:
            result = await self._binding.write(
                binding=str(binding.get("binding") or binding.get("name") or "sink"),
                location=binding.get("location"),
                data=data,
                contract_type=ctx.get("contract_type"),
                context=ctx,
            )
        except Exception as exc:
            self._sessions.pop(session.session_id, None)
            return CommitReceipt(
                status="rolled_back",
                session_id=session.session_id,
                provider=str(self._provider),
                message=str(exc),
            )
        self._sessions.pop(session.session_id, None)
        publication_id = None
        if isinstance(result, dict):
            publication_id = (
                result.get("publication_id")
                or result.get("digest")
                or result.get("path")
            )
            if publication_id is not None:
                publication_id = str(publication_id)
        return CommitReceipt(
            status="committed",
            session_id=session.session_id,
            provider=str(self._provider),
            publication_id=publication_id,
            metadata={"adapter": True},
        )

    async def abort(
        self,
        session: WriteSession,
        *,
        context: Mapping[str, Any],
    ) -> CommitReceipt:
        self._sessions.pop(session.session_id, None)
        return CommitReceipt(
            status="rolled_back",
            session_id=session.session_id,
            provider=str(self._provider),
            message="aborted",
            metadata={"adapter": True, **dict(context)},
        )

    async def reconcile(
        self,
        receipt: CommitReceipt,
        *,
        context: Mapping[str, Any],
    ) -> ReconciliationResult:
        # Legacy storage has no independent publication probe.
        return ReconciliationResult(
            status=receipt.status,
            publication_id=receipt.publication_id,
            message="StorageBindingAdapter cannot independently reconcile",
            metadata={"adapter": True, **dict(context)},
        )

    async def cleanup(
        self,
        receipt: CommitReceipt,
        *,
        context: Mapping[str, Any],
    ) -> CleanupReceipt:
        return CleanupReceipt(
            status="skipped",
            consume="none",
            message="StorageBindingAdapter has no cleanup",
            metadata={"adapter": True, **dict(context)},
        )

    async def inspect_schema(
        self,
        *,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> SchemaInspection:
        raise ConnectorCompatibilityError(
            "StorageBindingAdapter does not support schema inspection",
            code="PMCONN501",
            provider=str(self._provider),
        )

    def _require_session(self, session: WriteSession) -> dict[str, Any]:
        state = self._sessions.get(session.session_id)
        if state is None:
            raise ConnectorCompatibilityError(
                f"Unknown write session {session.session_id!r}",
                code="PMCONN502",
                provider=str(self._provider),
            )
        return state


__all__ = ["StorageBindingAdapter"]
