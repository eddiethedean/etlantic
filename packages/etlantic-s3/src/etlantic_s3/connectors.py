"""S3 source / sink / storage connectors (fake by default)."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from typing import Any

from etlantic.connectors.capabilities import (
    CLEANUP,
    IDEMPOTENCY,
    PUBLICATION_ATOMIC,
    RECONCILIATION,
    SOURCE_BATCH_SNAPSHOT,
    SOURCE_SCHEMA_DISCOVERY,
    SOURCE_STATISTICS_BOUNDED,
    WRITE_APPEND,
    WRITE_OVERWRITE,
)
from etlantic.connectors.errors import ConnectorConfigError, ConnectorWriteError
from etlantic.connectors.maturity import ConnectorMaturity
from etlantic.connectors.models import (
    SINK_PROTOCOL,
    SOURCE_PROTOCOL,
    STORAGE_PROTOCOL,
    CleanupReceipt,
    CommitReceipt,
    ConnectorInfo,
    CursorProposal,
    LandingReadManifest,
    ReadBatch,
    ReconciliationResult,
    SchemaInspection,
    SinkPlan,
    SourcePlan,
    WriteSession,
    fingerprint_public_config,
)
from etlantic_s3.fake import InMemoryS3Fake, boto3_available

PROVIDER = "s3"
PACKAGE_VERSION = "0.46.0"

S3_SOURCE_CAPS = frozenset(
    {
        SOURCE_BATCH_SNAPSHOT,
        SOURCE_SCHEMA_DISCOVERY,
        SOURCE_STATISTICS_BOUNDED,
        IDEMPOTENCY,
    }
)
S3_SINK_CAPS = frozenset(
    {
        WRITE_APPEND,
        WRITE_OVERWRITE,
        PUBLICATION_ATOMIC,
        RECONCILIATION,
        CLEANUP,
        IDEMPOTENCY,
    }
)
S3_STORAGE_CAPS = frozenset(
    {
        SOURCE_SCHEMA_DISCOVERY,
        SOURCE_STATISTICS_BOUNDED,
    }
)


def _public_config(binding: Mapping[str, Any]) -> dict[str, Any]:
    raw = binding.get("config")
    if isinstance(raw, dict):
        return dict(raw)
    keys = ("bucket", "prefix", "pointer_key", "format", "mode", "root_ref")
    return {k: binding[k] for k in keys if k in binding and binding[k] is not None}


def _bucket(binding: Mapping[str, Any], cfg: Mapping[str, Any]) -> str:
    bucket = str(
        cfg.get("bucket") or binding.get("location") or binding.get("bucket") or ""
    )
    if not bucket:
        raise ConnectorConfigError(
            "s3 binding requires bucket (config.bucket or location)",
            code="PMCONN801",
            provider=PROVIDER,
        )
    return bucket


@dataclass
class S3SourceConnector:
    """Read committed S3 objects via commit-pointer resolution."""

    backend: InMemoryS3Fake = field(default_factory=InMemoryS3Fake)
    force_fake: bool = True

    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name=PROVIDER,
            protocol=SOURCE_PROTOCOL,
            version=PACKAGE_VERSION,
            provider=PROVIDER,
            capabilities=tuple(sorted(S3_SOURCE_CAPS)),
            maturity=ConnectorMaturity.EXPERIMENTAL,
            metadata={
                "format": "json",
                "fake": self.force_fake or not boto3_available(),
                "live_aws": "opt-in-later",
            },
        )

    async def plan_read(
        self,
        *,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> SourcePlan:
        cfg = _public_config(binding)
        bucket = _bucket(binding, cfg)
        pointer = str(cfg.get("pointer_key") or f"{cfg.get('prefix') or ''}.commit")
        return SourcePlan(
            provider=PROVIDER,
            protocol=SOURCE_PROTOCOL,
            mode="snapshot",
            identity_scheme="s3_object_etag/1",
            listing_intent={
                "bucket": bucket,
                "pointer_key": pointer,
                "format": cfg.get("format") or "json",
            },
            config_fingerprint=fingerprint_public_config(cfg),
            root_ref=str(cfg.get("root_ref") or bucket),
            secret_refs=tuple(
                sorted(str(k) for k in (binding.get("secret_refs") or {}))
            ),
        )

    async def read_batches(
        self,
        *,
        plan: SourcePlan,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> AsyncIterator[ReadBatch]:
        intent = dict(plan.listing_intent)
        bucket = str(intent["bucket"])
        pointer = str(intent["pointer_key"])
        resolved = self.backend.get_committed_object(bucket=bucket, pointer_key=pointer)
        if resolved is None:
            yield ReadBatch(records=(), batch_index=0, exhausted=True)
            return
        data_key, payload = resolved
        try:
            records: tuple[Any, ...] = tuple(json.loads(payload.decode("utf-8")))
            if not isinstance(records, tuple):
                records = (records,)
        except (UnicodeDecodeError, json.JSONDecodeError):
            records = (payload,)
        yield ReadBatch(
            records=records,
            batch_index=0,
            exhausted=True,
            metadata={"bucket": bucket, "data_key": data_key, "pointer_key": pointer},
        )

    async def propose_cursor(
        self,
        *,
        plan: SourcePlan,
        manifest: LandingReadManifest,
        context: Mapping[str, Any],
    ) -> CursorProposal | None:
        return None


@dataclass
class S3SinkConnector:
    """Stage multipart uploads; commit via conditional pointer publication."""

    backend: InMemoryS3Fake = field(default_factory=InMemoryS3Fake)
    force_fake: bool = True
    _sessions: dict[str, dict[str, Any]] = field(default_factory=dict, repr=False)

    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name=PROVIDER,
            protocol=SINK_PROTOCOL,
            version=PACKAGE_VERSION,
            provider=PROVIDER,
            capabilities=tuple(sorted(S3_SINK_CAPS)),
            maturity=ConnectorMaturity.EXPERIMENTAL,
            metadata={
                "format": "json",
                "fake": self.force_fake or not boto3_available(),
                "multipart": True,
                "commit_pointer": "conditional",
            },
        )

    async def plan_write(
        self,
        *,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> SinkPlan:
        cfg = _public_config(binding)
        bucket = _bucket(binding, cfg)
        mode = str(cfg.get("mode") or binding.get("mode") or "overwrite")
        if mode not in {"append", "overwrite", "create", "create_only", "first_write"}:
            raise ConnectorConfigError(
                f"unsupported s3 write mode {mode!r}",
                code="PMCONN802",
                provider=PROVIDER,
            )
        return SinkPlan(
            provider=PROVIDER,
            protocol=SINK_PROTOCOL,
            write_mode=mode,
            required_capabilities=tuple(
                str(x)
                for x in (
                    binding.get("required_capabilities")
                    or cfg.get("required_capabilities")
                    or ()
                )
            ),
            config_fingerprint=fingerprint_public_config(cfg),
            root_ref=str(cfg.get("root_ref") or bucket),
            secret_refs=tuple(
                sorted(str(k) for k in (binding.get("secret_refs") or {}))
            ),
            metadata={
                "bucket": bucket,
                "prefix": cfg.get("prefix") or "",
                "pointer_key": cfg.get("pointer_key")
                or f"{cfg.get('prefix') or 'dataset'}.commit",
            },
        )

    async def begin_write(
        self,
        *,
        plan: SinkPlan,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> WriteSession:
        meta = dict(plan.metadata)
        bucket = str(meta["bucket"])
        prefix = str(meta.get("prefix") or "dataset")
        run_id = str(context.get("run_id") or uuid.uuid4().hex[:8])
        data_key = f"{prefix}/data/{run_id}.json"
        upload_id = self.backend.create_multipart_upload(bucket=bucket, key=data_key)
        session_id = f"s3-{uuid.uuid4().hex[:12]}"
        self._sessions[session_id] = {
            "upload_id": upload_id,
            "bucket": bucket,
            "data_key": data_key,
            "pointer_key": str(meta["pointer_key"]),
            "write_mode": plan.write_mode or "overwrite",
            "records": [],
            "parts": 0,
            "prepared": False,
            "data_etag": None,
            "status": "open",
        }
        return WriteSession(
            session_id=session_id,
            provider=PROVIDER,
            protocol=SINK_PROTOCOL,
            metadata={"upload_id": upload_id, "data_key": data_key},
        )

    async def write_batch(
        self,
        session: WriteSession,
        batch: Any,
        *,
        context: Mapping[str, Any],
    ) -> None:
        state = self._require_session(session.session_id)
        if state["status"] != "open":
            raise ConnectorWriteError(
                f"s3 session not open: {state['status']}",
                code="PMCONN810",
                provider=PROVIDER,
            )
        records = state["records"]
        if isinstance(batch, Mapping):
            records.append(dict(batch))
        elif isinstance(batch, (list, tuple)):
            for item in batch:
                if isinstance(item, Mapping):
                    records.append(dict(item))
                else:
                    records.append(item)
        elif isinstance(batch, (bytes, bytearray)):
            try:
                parsed = json.loads(bytes(batch).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ConnectorWriteError(
                    "s3 JSON sink expects UTF-8 JSON bytes",
                    code="PMCONN812",
                    provider=PROVIDER,
                ) from exc
            if isinstance(parsed, list):
                records.extend(parsed)
            else:
                records.append(parsed)
        elif isinstance(batch, str):
            try:
                parsed = json.loads(batch)
            except json.JSONDecodeError as exc:
                raise ConnectorWriteError(
                    "s3 JSON sink expects JSON text",
                    code="PMCONN812",
                    provider=PROVIDER,
                ) from exc
            if isinstance(parsed, list):
                records.extend(parsed)
            else:
                records.append(parsed)
        else:
            records.append(batch)

    async def prepare(
        self,
        session: WriteSession,
        *,
        context: Mapping[str, Any],
    ) -> None:
        state = self._require_session(session.session_id)
        # Serialize once — never multipart-concat separate JSON arrays.
        body = json.dumps(list(state["records"]), default=str).encode("utf-8")
        self.backend.upload_part(
            upload_id=str(state["upload_id"]),
            part_number=1,
            body=body,
        )
        state["parts"] = 1
        etag = self.backend.complete_multipart_upload(upload_id=str(state["upload_id"]))
        state["data_etag"] = etag
        state["prepared"] = True

    async def commit(
        self,
        session: WriteSession,
        *,
        context: Mapping[str, Any],
    ) -> CommitReceipt:
        state = self._require_session(session.session_id)
        if not state.get("prepared"):
            await self.prepare(session, context=context)
        # Create/first-write modes keep conditional create; overwrite/append replace.
        write_mode = str(state.get("write_mode") or "overwrite")
        if_none_match = write_mode in {"create", "create_only", "first_write"}
        result = self.backend.put_commit_pointer(
            bucket=str(state["bucket"]),
            pointer_key=str(state["pointer_key"]),
            data_key=str(state["data_key"]),
            if_none_match=if_none_match,
        )
        if not result.get("ok"):
            state["status"] = "unknown"
            return CommitReceipt(
                status="unknown",
                session_id=session.session_id,
                provider=PROVIDER,
                publication_id=None,
                message="conditional commit pointer failed",
                metadata={
                    "reason": result.get("status"),
                    "existing": result.get("existing"),
                    "bucket": state["bucket"],
                    "pointer_key": state["pointer_key"],
                    "data_key": state["data_key"],
                    "data_etag": state.get("data_etag"),
                },
            )
        state["status"] = "committed"
        return CommitReceipt(
            status="committed",
            session_id=session.session_id,
            provider=PROVIDER,
            publication_id=str(state["pointer_key"]),
            message="commit pointer published",
            metadata={
                "bucket": state["bucket"],
                "data_key": state["data_key"],
                "pointer_key": state["pointer_key"],
                "data_etag": state.get("data_etag"),
                "pointer_etag": result.get("etag"),
            },
        )

    async def abort(
        self,
        session: WriteSession,
        *,
        context: Mapping[str, Any],
    ) -> CommitReceipt:
        state = self._require_session(session.session_id)
        upload_id = str(state["upload_id"])
        self.backend.abort_multipart_upload(upload_id=upload_id)
        # Orphan cleanup: remove completed-but-unpublished data objects.
        if state.get("prepared") and state.get("status") != "committed":
            self.backend.delete_object(
                bucket=str(state["bucket"]), key=str(state["data_key"])
            )
        state["status"] = "aborted"
        return CommitReceipt(
            status="rolled_back",
            session_id=session.session_id,
            provider=PROVIDER,
            message="multipart aborted",
            metadata={"upload_id": upload_id},
        )

    async def reconcile(
        self,
        receipt: CommitReceipt,
        *,
        context: Mapping[str, Any],
    ) -> ReconciliationResult:
        meta = dict(receipt.metadata)
        bucket = str(meta.get("bucket") or context.get("bucket") or "")
        pointer = str(meta.get("pointer_key") or receipt.publication_id or "")
        data_key = str(meta.get("data_key") or "")
        if not bucket or not pointer:
            return ReconciliationResult(
                status="unknown",
                message="insufficient evidence to reconcile",
                metadata=meta,
            )
        resolved = self.backend.get_committed_object(bucket=bucket, pointer_key=pointer)
        if resolved is None:
            return ReconciliationResult(
                status="rolled_back",
                publication_id=None,
                message="no committed pointer",
                metadata=meta,
            )
        committed_key, _ = resolved
        if data_key and committed_key != data_key:
            return ReconciliationResult(
                status="rolled_back",
                publication_id=pointer,
                message="another writer won the commit pointer",
                metadata={**meta, "committed_data_key": committed_key},
            )
        return ReconciliationResult(
            status="committed",
            publication_id=pointer,
            message="pointer resolves to this publication",
            metadata={**meta, "committed_data_key": committed_key},
        )

    async def cleanup(
        self,
        receipt: CommitReceipt,
        *,
        context: Mapping[str, Any],
    ) -> CleanupReceipt:
        return CleanupReceipt(status="skipped", message="no consume policy for s3 fake")

    def _require_session(self, session_id: str) -> dict[str, Any]:
        state = self._sessions.get(session_id)
        if state is None:
            raise ConnectorWriteError(
                f"unknown s3 write session {session_id!r}",
                code="PMCONN811",
                provider=PROVIDER,
            )
        return state


@dataclass
class S3StorageConnector:
    """Bounded schema inspection over committed S3 objects."""

    backend: InMemoryS3Fake = field(default_factory=InMemoryS3Fake)
    force_fake: bool = True

    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name=PROVIDER,
            protocol=STORAGE_PROTOCOL,
            version=PACKAGE_VERSION,
            provider=PROVIDER,
            capabilities=tuple(sorted(S3_STORAGE_CAPS)),
            maturity=ConnectorMaturity.EXPERIMENTAL,
            metadata={"fake": self.force_fake or not boto3_available()},
        )

    async def inspect_schema(
        self,
        *,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> SchemaInspection:
        cfg = _public_config(binding)
        bucket = _bucket(binding, cfg)
        pointer = str(
            cfg.get("pointer_key") or f"{cfg.get('prefix') or 'dataset'}.commit"
        )
        resolved = self.backend.get_committed_object(bucket=bucket, pointer_key=pointer)
        if resolved is None:
            return SchemaInspection(
                provider=PROVIDER,
                fields=(),
                row_estimate=0,
                byte_estimate=0,
                metadata={"bucket": bucket, "pointer_key": pointer, "committed": False},
            )
        data_key, payload = resolved
        fields: list[dict[str, Any]] = []
        row_estimate = 0
        try:
            parsed = json.loads(payload.decode("utf-8"))
            if isinstance(parsed, list):
                row_estimate = len(parsed)
                if parsed and isinstance(parsed[0], dict):
                    fields = [
                        {"name": k, "type": type(v).__name__}
                        for k, v in parsed[0].items()
                    ]
            elif isinstance(parsed, dict):
                row_estimate = 1
                fields = [
                    {"name": k, "type": type(v).__name__} for k, v in parsed.items()
                ]
        except (UnicodeDecodeError, json.JSONDecodeError):
            fields = [{"name": "_bytes", "type": "binary"}]
            row_estimate = None
        return SchemaInspection(
            provider=PROVIDER,
            fields=tuple(fields),
            row_estimate=row_estimate,
            byte_estimate=len(payload),
            metadata={
                "bucket": bucket,
                "pointer_key": pointer,
                "data_key": data_key,
                "committed": True,
            },
        )


def create_source() -> S3SourceConnector:
    """Entry-point factory for ``etlantic.source_connectors``."""
    return S3SourceConnector()


def create_sink() -> S3SinkConnector:
    """Entry-point factory for ``etlantic.sink_connectors``."""
    return S3SinkConnector()


def create_storage() -> S3StorageConnector:
    """Entry-point factory for ``etlantic.storage_connectors``."""
    return S3StorageConnector()


__all__ = [
    "S3SinkConnector",
    "S3SourceConnector",
    "S3StorageConnector",
    "create_sink",
    "create_source",
    "create_storage",
]
