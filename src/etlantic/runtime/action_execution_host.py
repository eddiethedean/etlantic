"""Separate deadline-bound worker for authorized connector action jobs."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import inspect
import json
import re
import threading
from collections.abc import Awaitable, Callable, Mapping
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any, cast

from etlantic.control_plane.action_jobs import (
    MAX_PREVIEW_RESULT_TTL_SECONDS,
    MIN_PREVIEW_RESULT_TTL_SECONDS,
    ConnectorActionKind,
    ConnectorCatalogRequest,
    ConnectorPreviewRequest,
    ConnectorProvisionCleanupRequest,
    ConnectorProvisionRequest,
    connector_action_resources,
    parse_connector_action_request,
    verify_provision_parent,
)
from etlantic.control_plane.authz import require_authorized
from etlantic.control_plane.durable_models import ActionJobRecord
from etlantic.control_plane.durable_protocols import DurableWorkStore
from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.models import (
    ControlPlaneContext,
    EnvironmentRef,
    Principal,
    PrincipalKind,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic.control_plane.protocols import Authorizer
from etlantic.control_plane.redaction import REDACTED, redact_control_plane_payload

ActionHandler = Callable[
    [ControlPlaneContext, Mapping[str, Any]], Awaitable[Mapping[str, Any]]
]
_MAX_RESULT_DEPTH = 32
_MAX_TICK_LIMIT = 100
_SAFE_EFFECT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}\Z")
_SAFE_PREVIEW_COLUMN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}\Z")


class _ActionLeaseLost(Exception):
    """Raised when an ordinary action handler can no longer renew its lease."""

    def __init__(self, result: Mapping[str, Any] | None = None) -> None:
        super().__init__("Action worker lease renewal failed")
        self.result = result


def _now() -> datetime:
    return datetime.now(UTC)


class ActionExecutionHost:
    """Claim action jobs and invoke async provider handlers outside HTTP routes.

    Handler coroutines receive a trusted context reconstructed from the accepted
    job and must honor cancellation. Their returned receipt is redacted and
    limited before it is persisted. No request thread or FastAPI background task
    participates in execution.
    """

    def __init__(
        self,
        durable: DurableWorkStore,
        *,
        handlers: Mapping[str, ActionHandler] | None = None,
        authorizer: Authorizer,
        profile: Any = None,
        worker_id: str = "action-worker-1",
        lease_seconds: int = 30,
        max_result_bytes: int = 64 * 1024,
        max_result_items: int = 100,
        preview_result_ttl_seconds: int = 60 * 60,
    ) -> None:
        if not worker_id.strip():
            raise ValueError("worker_id must be non-empty")
        if type(lease_seconds) is not int or lease_seconds < 1:
            raise ValueError("lease_seconds must be a positive integer")
        if type(max_result_bytes) is not int or max_result_bytes < 1:
            raise ValueError("max_result_bytes must be a positive integer")
        if type(max_result_items) is not int or max_result_items < 1:
            raise ValueError("max_result_items must be a positive integer")
        if (
            type(preview_result_ttl_seconds) is not int
            or not MIN_PREVIEW_RESULT_TTL_SECONDS
            <= preview_result_ttl_seconds
            <= MAX_PREVIEW_RESULT_TTL_SECONDS
        ):
            raise ValueError(
                "preview_result_ttl_seconds must be between "
                f"{MIN_PREVIEW_RESULT_TTL_SECONDS} and "
                f"{MAX_PREVIEW_RESULT_TTL_SECONDS} seconds"
            )
        self.durable = durable
        self.authorizer = authorizer
        self.handlers: dict[str, ActionHandler] = dict(handlers or {})
        self.profile = profile
        if profile is not None:
            self.handlers.setdefault("connector.catalog", self._catalog_page)
        for name, handler in self.handlers.items():
            if not callable(handler) or not (
                inspect.iscoroutinefunction(handler)
                or inspect.iscoroutinefunction(type(handler).__call__)
            ):
                raise TypeError(f"action handler {name!r} must be asynchronous")
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds
        self.max_result_bytes = max_result_bytes
        self.max_result_items = max_result_items
        self.preview_result_ttl_seconds = preview_result_ttl_seconds

    def tick(self, ctx: ControlPlaneContext, *, limit: int = 20) -> int:
        """Execute at most ``limit`` currently available action jobs."""
        if type(limit) is not int or not 1 <= limit <= _MAX_TICK_LIMIT:
            raise ValueError(f"limit must be between 1 and {_MAX_TICK_LIMIT}")
        self.durable.cleanup_expired_action_results(ctx, limit=100)
        processed = 0
        for _ in range(limit):
            job = self.durable.claim_action_job(
                ctx,
                worker_id=self.worker_id,
                lease_seconds=self.lease_seconds,
            )
            if job is None:
                break
            handler = self.handlers.get(job.action)
            if handler is None:
                self._finish_failure(ctx, job, "handler_unavailable")
                processed += 1
                continue
            if job.action == "run.prepare":
                self._execute_run_preparation(ctx, job, handler)
                processed += 1
                continue
            try:
                raw_request = json.loads(job.request_json)
                if not isinstance(raw_request, dict):
                    raise ValueError("action request must be an object")
                request = cast(dict[str, Any], raw_request)
                typed_action = cast(ConnectorActionKind, job.action)
                typed_request = parse_connector_action_request(typed_action, request)
                request: dict[str, Any] = typed_request.to_dict()
                action_ctx = self._trusted_context(ctx, job)
            except Exception:
                self._finish_failure(ctx, job, "invalid_action_request")
                processed += 1
                continue
            try:
                for resource in connector_action_resources(typed_action, typed_request):
                    require_authorized(
                        self.authorizer,
                        action_ctx,
                        job.action,
                        resource,
                        resource_in_caller_scope=True,
                    )
            except ControlPlaneError:
                self._finish_failure(ctx, job, "authorization_denied")
                processed += 1
                continue
            provision_effect: Mapping[str, Any] | None = None
            retain_effect_callback: Callable[[Mapping[str, Any]], None] | None = None
            try:
                if isinstance(typed_request, ConnectorProvisionCleanupRequest):
                    parent = self.durable.get_action_job(
                        action_ctx, typed_request.provision_action_id
                    )
                    provision, provision_effect = verify_provision_parent(
                        action_ctx, typed_request, parent
                    )
                    request.update(
                        {
                            "action_id": job.action_id,
                            "effect_id": provision_effect["effect_id"],
                            "schema_fingerprint": provision.schema_fingerprint(),
                            "target_kind": provision.target_kind,
                        }
                    )
                elif isinstance(typed_request, ConnectorProvisionRequest):
                    request.update(
                        {
                            "action_id": job.action_id,
                            "mode": "create_only",
                            "if_exists": "fail",
                            "schema_fingerprint": typed_request.schema_fingerprint(),
                        }
                    )
                elif isinstance(typed_request, ConnectorPreviewRequest):
                    request["max_rows"] = min(
                        typed_request.max_rows, self.max_result_items
                    )
                    request["max_bytes"] = min(
                        typed_request.max_bytes, self.max_result_bytes
                    )
            except ControlPlaneError as exc:
                failure = (
                    "authorization_denied"
                    if exc.status in {403, 404}
                    else "provision_parent_unavailable"
                )
                self._finish_failure(ctx, job, failure)
                processed += 1
                continue
            except Exception:
                self._finish_failure(ctx, job, "invalid_action_request")
                processed += 1
                continue
            if (
                isinstance(typed_request, ConnectorCatalogRequest)
                and typed_request.provider == "postgresql"
            ):
                # The PostgreSQL handler receives the trusted job deadline,
                # never a caller-supplied internal execution control.
                request["_deadline_at"] = job.deadline_at
            deadline = datetime.fromisoformat(job.deadline_at.replace("Z", "+00:00"))
            remaining = (deadline - _now()).total_seconds()
            if remaining <= 0:
                self._finish_timeout(ctx, job)
                processed += 1
                continue
            if isinstance(
                typed_request,
                (ConnectorProvisionRequest, ConnectorProvisionCleanupRequest),
            ):
                # Worker-only controls are never accepted from or persisted in
                # the public action request.
                request["_deadline_at"] = job.deadline_at

                def retain_effect(
                    result: Mapping[str, Any],
                    effect_request: ConnectorProvisionRequest
                    | ConnectorProvisionCleanupRequest = typed_request,
                    effect_job: ActionJobRecord = job,
                    effect_ctx: ControlPlaneContext = action_ctx,
                    parent_effect: Mapping[str, Any] | None = provision_effect,
                ) -> None:
                    valid = (
                        self._valid_provision_effect(
                            effect_request, effect_job.action_id, result
                        )
                        if isinstance(effect_request, ConnectorProvisionRequest)
                        else self._valid_cleanup_effect(
                            effect_request, effect_job.action_id, parent_effect, result
                        )
                    )
                    if not valid:
                        raise ValueError("invalid late action effect receipt")
                    self.durable.finish_action_job(
                        effect_ctx,
                        effect_job.action_id,
                        worker_id=self.worker_id,
                        fencing_token=effect_job.fencing_token,
                        status="succeeded",
                        result=self._bounded_result(result),
                    )

                request["_retain_effect"] = retain_effect
                retain_effect_callback = retain_effect
            try:
                result = asyncio.run(
                    self._run_action_handler(
                        action_ctx, job, handler, request, deadline=deadline
                    )
                )
            except _ActionLeaseLost as lost:
                # A cancelled provision may still return proof of a committed
                # effect. Retain it only through the original worker fence.
                if lost.result is not None and retain_effect_callback is not None:
                    with suppress(Exception):
                        retain_effect_callback(lost.result)
                processed += 1
                continue
            except TimeoutError:
                if (
                    datetime.fromisoformat(job.deadline_at.replace("Z", "+00:00"))
                    <= _now()
                ):
                    self._finish_timeout(ctx, job)
                else:
                    self._finish_failure(ctx, job, "provider_timeout")
                processed += 1
                continue
            except Exception:
                # Provider exception codes and messages are untrusted. Never
                # persist provider-controlled text in a caller-visible receipt.
                self._finish_failure(ctx, job, "action_failed")
                processed += 1
                continue
            if isinstance(typed_request, ConnectorPreviewRequest):
                try:
                    result = self._bounded_preview_result(
                        typed_request,
                        result,
                        max_rows=min(typed_request.max_rows, self.max_result_items),
                        max_bytes=min(typed_request.max_bytes, self.max_result_bytes),
                    )
                except Exception:
                    self._finish_failure(ctx, job, "result_limit_exceeded")
                    processed += 1
                    continue
            elif isinstance(typed_request, ConnectorProvisionRequest):
                if not self._valid_provision_effect(
                    typed_request, job.action_id, result
                ):
                    self._finish_failure(ctx, job, "invalid_effect_receipt")
                    processed += 1
                    continue
            elif isinstance(
                typed_request, ConnectorProvisionCleanupRequest
            ) and not self._valid_cleanup_effect(
                typed_request, job.action_id, provision_effect, result
            ):
                self._finish_failure(ctx, job, "invalid_effect_receipt")
                processed += 1
                continue
            try:
                safe_result = self._bounded_result(result)
            except Exception:
                self._finish_failure(ctx, job, "result_limit_exceeded")
                processed += 1
                continue
            self.durable.finish_action_job(
                ctx,
                job.action_id,
                worker_id=self.worker_id,
                fencing_token=job.fencing_token,
                status="succeeded",
                result=safe_result,
                result_ttl_seconds=(
                    self.preview_result_ttl_seconds
                    if isinstance(typed_request, ConnectorPreviewRequest)
                    else None
                ),
            )
            processed += 1
        return processed

    async def _run_action_handler(
        self,
        ctx: ControlPlaneContext,
        job: ActionJobRecord,
        handler: ActionHandler,
        request: Mapping[str, Any],
        *,
        deadline: datetime,
    ) -> Mapping[str, Any]:
        """Run an ordinary handler while renewing its fenced action lease."""

        async def invoke() -> Mapping[str, Any]:
            return await handler(ctx, request)

        task = asyncio.create_task(invoke())
        interval = min(1.0, max(0.05, self.lease_seconds / 3))
        while not task.done():
            remaining = (deadline - _now()).total_seconds()
            if remaining <= 0:
                task.cancel()
                try:
                    return await self._await_cancelled_action_handler(ctx, job, task)
                except _ActionLeaseLost:
                    raise
                except (asyncio.CancelledError, Exception):
                    raise TimeoutError from None
            await asyncio.wait({task}, timeout=min(interval, remaining))
            if task.done():
                break
            if _now() >= deadline:
                continue
            try:
                self.durable.heartbeat_action_job(
                    ctx,
                    job.action_id,
                    worker_id=self.worker_id,
                    fencing_token=job.fencing_token,
                    lease_seconds=self.lease_seconds,
                )
            except Exception as exc:
                task.cancel()
                try:
                    result = await task
                except (asyncio.CancelledError, Exception):
                    raise _ActionLeaseLost from exc
                raise _ActionLeaseLost(result) from exc
        return await task

    async def _await_cancelled_action_handler(
        self,
        ctx: ControlPlaneContext,
        job: ActionJobRecord,
        task: asyncio.Task[Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        """Drain a cancelled handler without letting its lease expire."""
        interval = min(1.0, max(0.05, self.lease_seconds / 3))
        while not task.done():
            await asyncio.wait({task}, timeout=interval)
            if task.done():
                break
            try:
                self.durable.heartbeat_action_job(
                    ctx,
                    job.action_id,
                    worker_id=self.worker_id,
                    fencing_token=job.fencing_token,
                    lease_seconds=self.lease_seconds,
                )
            except Exception as exc:
                try:
                    current = self.durable.get_action_job(ctx, job.action_id)
                except Exception:
                    current = None
                if (
                    current is not None
                    and current.fencing_token == job.fencing_token
                    and current.status in {"timed_out", "cancelled"}
                ):
                    # Keep draining when another claimant terminalized this
                    # expired job under the same fence.
                    try:
                        result = await task
                    except (asyncio.CancelledError, Exception):
                        raise _ActionLeaseLost from exc
                    raise _ActionLeaseLost(result) from exc
                task.cancel()
                try:
                    result = await task
                except (asyncio.CancelledError, Exception):
                    raise _ActionLeaseLost from exc
                raise _ActionLeaseLost(result) from exc
        return await task

    def _execute_run_preparation(
        self,
        worker_ctx: ControlPlaneContext,
        job: ActionJobRecord,
        handler: ActionHandler,
    ) -> None:
        try:
            raw = json.loads(job.request_json)
            if not isinstance(raw, dict) or set(cast(dict[str, Any], raw)) != {
                "definition_id",
                "revision_selector",
                "profile_name",
                "run_request",
                "definition_revision_id",
            }:
                raise ValueError("invalid run preparation intent")
            request = cast(dict[str, Any], raw)
            if not all(
                isinstance(request.get(name), str)
                for name in (
                    "definition_id",
                    "revision_selector",
                    "profile_name",
                    "definition_revision_id",
                )
            ) or not isinstance(request.get("run_request"), dict):
                raise ValueError("invalid run preparation intent")
            action_ctx = self._trusted_context(worker_ctx, job)
            require_authorized(
                self.authorizer,
                action_ctx,
                "run.submit",
                f"definition:{request['definition_id']}",
                resource_in_caller_scope=False,
            )
        except ControlPlaneError as exc:
            self._finish_failure(
                worker_ctx,
                job,
                "authorization_denied"
                if exc.status in {403, 404}
                else "invalid_action_request",
            )
            return
        except Exception:
            self._finish_failure(worker_ctx, job, "invalid_action_request")
            return

        cancel_event = threading.Event()
        request["_operation_id"] = job.action_id
        request["_worker_id"] = self.worker_id
        request["_fencing_token"] = job.fencing_token
        request["_cancel_event"] = cancel_event
        deadline = datetime.fromisoformat(job.deadline_at.replace("Z", "+00:00"))
        try:
            result = asyncio.run(
                self._run_preparation_handler(
                    action_ctx,
                    job,
                    handler,
                    request,
                    cancel_event,
                    deadline=deadline,
                )
            )
            safe_result = self._bounded_result(result)
            self.durable.finish_action_job(
                action_ctx,
                job.action_id,
                worker_id=self.worker_id,
                fencing_token=job.fencing_token,
                status="succeeded",
                result=safe_result,
            )
        except TimeoutError:
            self._finish_timeout(action_ctx, job)
        except Exception:
            self._finish_failure(action_ctx, job, "preparation_failed")

    async def _run_preparation_handler(
        self,
        ctx: ControlPlaneContext,
        job: ActionJobRecord,
        handler: ActionHandler,
        request: Mapping[str, Any],
        cancel_event: threading.Event,
        *,
        deadline: datetime,
    ) -> Mapping[str, Any]:
        async def invoke() -> Mapping[str, Any]:
            return await handler(ctx, request)

        task = asyncio.create_task(invoke())
        interval = min(1.0, max(0.05, self.lease_seconds / 3))
        timed_out = False
        while not task.done():
            await asyncio.wait({task}, timeout=interval)
            if task.done():
                break
            operation = self.durable.get_action_job(ctx, job.action_id)
            if operation.status == "cancel_requested":
                cancel_event.set()
            if _now() >= deadline:
                timed_out = True
                cancel_event.set()
            self.durable.heartbeat_action_job(
                ctx,
                job.action_id,
                worker_id=self.worker_id,
                fencing_token=job.fencing_token,
                lease_seconds=self.lease_seconds,
            )
        try:
            result = await task
        except Exception:
            if timed_out or _now() >= deadline:
                raise TimeoutError from None
            raise
        if timed_out or _now() >= deadline:
            operation = self.durable.get_action_job(ctx, job.action_id)
            if operation.phase != "accepting":
                raise TimeoutError
            # Acceptance is a durable side effect. Return its receipt even when
            # it completed after the deadline; finish_action_job keeps the
            # operation timed out while retaining that receipt for recovery.
        return result

    @staticmethod
    def _valid_provision_effect(
        request: ConnectorProvisionRequest,
        action_id: str,
        result: Mapping[str, Any],
    ) -> bool:
        if set(result) != {
            "action_id",
            "effect_id",
            "resource_id",
            "schema_fingerprint",
            "created",
            "cleanup_supported",
        }:
            return False
        effect_id = result.get("effect_id")
        return (
            isinstance(effect_id, str)
            and _SAFE_EFFECT_ID.fullmatch(effect_id) is not None
            and result.get("action_id") == action_id
            and result.get("resource_id") == request.resource_id
            and result.get("schema_fingerprint") == request.schema_fingerprint()
            and result.get("created") is True
            and result.get("cleanup_supported") is True
        )

    @staticmethod
    def _valid_cleanup_effect(
        request: ConnectorProvisionCleanupRequest,
        action_id: str,
        provision_effect: Mapping[str, Any] | None,
        result: Mapping[str, Any],
    ) -> bool:
        if provision_effect is None:
            return False
        if set(result) != {
            "action_id",
            "effect_id",
            "resource_id",
            "cleanup_of",
            "removed",
        }:
            return False
        return (
            result.get("action_id") == action_id
            and result.get("effect_id") == provision_effect.get("effect_id")
            and result.get("resource_id") == request.resource_id
            and result.get("cleanup_of") == request.provision_action_id
            and result.get("removed") is True
        )

    @staticmethod
    def _bounded_preview_result(
        request: ConnectorPreviewRequest,
        result: Mapping[str, Any],
        *,
        max_rows: int,
        max_bytes: int,
    ) -> dict[str, Any]:
        if set(result) - {"columns", "rows", "truncated"}:
            raise ValueError("preview provider returned unsupported fields")
        columns_value = result.get("columns")
        rows_value = result.get("rows")
        truncated_value = result.get("truncated", False)
        if (
            not isinstance(columns_value, list)
            or not isinstance(rows_value, list)
            or type(truncated_value) is not bool
        ):
            raise ValueError("preview provider returned an invalid shape")
        columns_list = cast(list[Any], columns_value)
        rows_list = cast(list[Any], rows_value)
        if len(columns_list) > 100:
            raise ValueError("preview provider returned too many columns")
        columns: list[dict[str, Any]] = []
        sensitive_fields = set(request.redact_fields)
        names: set[str] = set()
        for raw_column in columns_list:
            if not isinstance(raw_column, Mapping):
                raise ValueError("preview column metadata is invalid")
            column = cast(Mapping[str, Any], raw_column)
            name = column.get("name")
            logical_type = column.get("logical_type", "unknown")
            sensitive = column.get("sensitive", False)
            if (
                not isinstance(name, str)
                or _SAFE_PREVIEW_COLUMN.fullmatch(name) is None
                or not isinstance(logical_type, str)
                or len(logical_type) > 64
                or type(sensitive) is not bool
                or name in names
                or set(column) - {"name", "logical_type", "sensitive"}
            ):
                raise ValueError("preview column metadata is invalid")
            names.add(name)
            if sensitive:
                sensitive_fields.add(name)
            columns.append({"name": name, "logical_type": logical_type})
        rows: list[dict[str, Any]] = []
        for raw_row in rows_list[:max_rows]:
            if not isinstance(raw_row, Mapping):
                raise ValueError("preview row is invalid")
            source = cast(Mapping[str, Any], raw_row)
            rows.append(
                {
                    name: REDACTED if name in sensitive_fields else source[name]
                    for name in names
                    if name in source
                }
            )
        truncated = truncated_value or len(rows_list) > max_rows
        safe = redact_control_plane_payload(
            {
                "schema": "etlantic.connector.preview/1",
                "columns": columns,
                "rows": rows,
                "truncated": truncated,
            }
        )
        if not isinstance(safe, dict):
            raise ValueError("preview redaction returned an invalid shape")
        payload = cast(dict[str, Any], safe)

        def encode() -> bytes:
            return json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")

        while len(encode()) > max_bytes and payload["rows"]:
            payload["rows"].pop()
            payload["truncated"] = True
        if len(encode()) > max_bytes:
            raise ValueError("preview schema exceeds the result byte limit")
        return payload

    @staticmethod
    def _trusted_context(
        worker_ctx: ControlPlaneContext, job: ActionJobRecord
    ) -> ControlPlaneContext:
        if (
            worker_ctx.tenant.tenant_id != job.tenant_id
            or worker_ctx.workspace.workspace_id != job.workspace_id
        ):
            raise ControlPlaneError.not_found("Action job not found")
        return ControlPlaneContext(
            principal=Principal(
                subject=job.principal_subject,
                issuer=job.principal_issuer,
                kind=cast(PrincipalKind, job.principal_kind),
            ),
            tenant=TenantRef(job.tenant_id),
            workspace=WorkspaceRef(job.tenant_id, job.workspace_id),
            environment=EnvironmentRef(job.environment),
            security_domain=SecurityDomain(job.security_domain_id),
            resource_owner_id=job.owner_id,
        )

    def _bounded_result(self, result: Mapping[str, Any]) -> dict[str, Any]:
        safe = redact_control_plane_payload(dict(result))
        if not isinstance(safe, dict):
            raise TypeError("action handler result must be a JSON object")
        safe_result = cast(dict[str, Any], safe)

        def check_shape(value: Any, depth: int) -> None:
            if depth > _MAX_RESULT_DEPTH:
                raise ValueError("action result exceeds its nesting limit")
            if isinstance(value, Mapping):
                children = cast(Mapping[str, Any], value).values()
                for child in children:
                    check_shape(child, depth + 1)
            elif isinstance(value, list):
                items = cast(list[Any], value)
                if len(items) > self.max_result_items:
                    raise ValueError("action result array exceeds its item limit")
                for child in items:
                    check_shape(child, depth + 1)

        check_shape(safe_result, 0)
        encoded = json.dumps(
            safe_result,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        if len(encoded) > self.max_result_bytes:
            raise ValueError("action result exceeds its byte limit")
        return safe_result

    def _finish_timeout(self, ctx: ControlPlaneContext, job: ActionJobRecord) -> None:
        try:
            self.durable.finish_action_job(
                ctx,
                job.action_id,
                worker_id=self.worker_id,
                fencing_token=job.fencing_token,
                status="timed_out",
                error_code="deadline_exceeded",
            )
        except ControlPlaneError as exc:
            # A late verified effect may have finalized the same fenced job
            # while its deadline handler was unwinding.
            current = self.durable.get_action_job(ctx, job.action_id)
            if not (
                exc.status == 409
                and current.fencing_token == job.fencing_token
                and current.status in {"timed_out", "cancelled"}
            ):
                raise

    async def _catalog_page(
        self, ctx: ControlPlaneContext, request: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """Return one stable page of profile-authorized installed connectors."""
        provider = request.get("provider")
        if isinstance(provider, str):
            handler = self.handlers.get(f"connector.catalog.{provider}")
            if handler is None:
                raise ValueError("live catalog is unavailable for this provider")
            return await handler(ctx, request)
        from etlantic.connectors.catalog import connector_catalog_for_profile
        from etlantic.profile import resolve_profile

        profile = resolve_profile(self.profile, allow_adhoc_profile=False)
        catalog = connector_catalog_for_profile(profile)
        entries_value = catalog.get("connectors")
        if not isinstance(entries_value, list):
            raise ValueError("connector catalog has an invalid shape")
        entries: list[Any] = cast(list[Any], entries_value)
        kind = request.get("kind")
        if kind is not None:
            filtered_entries: list[Any] = []
            for entry in entries:
                if (
                    isinstance(entry, dict)
                    and cast(dict[str, Any], entry).get("kind") == kind
                ):
                    filtered_entries.append(entry)
            entries = filtered_entries
        fingerprint = hashlib.sha256(
            json.dumps(catalog, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        limit = request.get("limit", 50)
        if type(limit) is not int or not 1 <= limit <= self.max_result_items:
            raise ValueError("catalog page limit is outside the supported bounds")
        cursor = request.get("cursor")
        offset = 0
        if cursor is not None:
            if not isinstance(cursor, str) or len(cursor) > 256:
                raise ValueError("catalog cursor is invalid")
            try:
                decoded_payload = json.loads(
                    base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
                )
                if not isinstance(decoded_payload, list):
                    raise ValueError("catalog cursor payload is invalid")
                payload = cast(list[Any], decoded_payload)
                if (
                    len(payload) != 2
                    or payload[0] != fingerprint
                    or type(payload[1]) is not int
                    or payload[1] < 0
                ):
                    raise ValueError("catalog cursor no longer matches this catalog")
                offset_value = payload[1]
                if type(offset_value) is not int:
                    raise ValueError("catalog cursor offset is invalid")
                offset = offset_value
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                raise ValueError("catalog cursor is invalid or stale") from exc
        page: list[Any] = entries[offset : offset + limit]
        next_cursor = None
        if offset + len(page) < len(entries):
            next_payload = json.dumps(
                [fingerprint, offset + len(page)], separators=(",", ":")
            ).encode("utf-8")
            next_cursor = (
                base64.urlsafe_b64encode(next_payload).decode("ascii").rstrip("=")
            )
        return {
            "schema": catalog.get("schema"),
            "items": page,
            "next_cursor": next_cursor,
            "has_more": next_cursor is not None,
        }

    def _finish_failure(
        self, ctx: ControlPlaneContext, job: ActionJobRecord, code: str
    ) -> None:
        self.durable.finish_action_job(
            ctx,
            job.action_id,
            worker_id=self.worker_id,
            fencing_token=job.fencing_token,
            status="failed",
            error_code=code,
        )


__all__ = ["ActionExecutionHost", "ActionHandler"]
