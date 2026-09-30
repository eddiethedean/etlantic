"""Separate deadline-bound worker for authorized connector action jobs."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import inspect
import json
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from typing import Any, cast

from etlantic.control_plane.action_jobs import (
    ConnectorActionKind,
    connector_action_resources,
    parse_connector_action_request,
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
from etlantic.control_plane.redaction import redact_control_plane_payload

ActionHandler = Callable[
    [ControlPlaneContext, Mapping[str, Any]], Awaitable[Mapping[str, Any]]
]
_MAX_RESULT_DEPTH = 32
_MAX_TICK_LIMIT = 100


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
    ) -> None:
        if not worker_id.strip():
            raise ValueError("worker_id must be non-empty")
        if type(lease_seconds) is not int or lease_seconds < 1:
            raise ValueError("lease_seconds must be a positive integer")
        if type(max_result_bytes) is not int or max_result_bytes < 1:
            raise ValueError("max_result_bytes must be a positive integer")
        if type(max_result_items) is not int or max_result_items < 1:
            raise ValueError("max_result_items must be a positive integer")
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

    def tick(self, ctx: ControlPlaneContext, *, limit: int = 20) -> int:
        """Execute at most ``limit`` currently available action jobs."""
        if type(limit) is not int or not 1 <= limit <= _MAX_TICK_LIMIT:
            raise ValueError(f"limit must be between 1 and {_MAX_TICK_LIMIT}")
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
            try:
                raw_request = json.loads(job.request_json)
                if not isinstance(raw_request, dict):
                    raise ValueError("action request must be an object")
                request = cast(dict[str, Any], raw_request)
                typed_action = cast(ConnectorActionKind, job.action)
                typed_request = parse_connector_action_request(
                    typed_action, request
                )
                request = typed_request.to_dict()
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
            deadline = datetime.fromisoformat(
                job.deadline_at.replace("Z", "+00:00")
            )
            remaining = (deadline - _now()).total_seconds()
            if remaining <= 0:
                self._finish_timeout(ctx, job)
                processed += 1
                continue
            try:
                result = asyncio.run(
                    asyncio.wait_for(handler(action_ctx, request), timeout=remaining)
                )
            except TimeoutError:
                if datetime.fromisoformat(
                    job.deadline_at.replace("Z", "+00:00")
                ) <= _now():
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
            )
            processed += 1
        return processed

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

    def _finish_timeout(
        self, ctx: ControlPlaneContext, job: ActionJobRecord
    ) -> None:
        self.durable.finish_action_job(
            ctx,
            job.action_id,
            worker_id=self.worker_id,
            fencing_token=job.fencing_token,
            status="timed_out",
            error_code="deadline_exceeded",
        )

    async def _catalog_page(
        self, _ctx: ControlPlaneContext, request: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """Return one stable page of profile-authorized installed connectors."""
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
            json.dumps(catalog, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
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
