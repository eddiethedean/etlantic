"""Canonical defaults and validation for managed backend settings.

Transport and storage adapters retain their established configuration classes,
but delegate shared policy to this core module. HTTP-only presentation settings
and provider connection ownership remain in their respective adapters.
"""

from __future__ import annotations

import inspect
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, cast

from etlantic.control_plane.action_jobs import (
    MAX_PREVIEW_RESULT_TTL_SECONDS,
    MIN_PREVIEW_RESULT_TTL_SECONDS,
)
from etlantic.control_plane.durable_models import validate_execution_route
from etlantic.control_plane.event_retention import (
    DEFAULT_EVENT_IDEMPOTENCY_RETENTION_SECONDS,
)


def empty_managed_mapping() -> dict[str, Any]:
    """Return a fresh mapping for a managed setting with no entries."""
    return {}


MANAGED_BACKEND_DEFAULTS: Mapping[str, Any] = MappingProxyType(
    {
        "database_url": None,
        "store_id": "default",
        "profile": "development",
        "engine_options": empty_managed_mapping,
        "event_retention_max_events_per_scope": 100_000,
        "event_idempotency_retention_seconds": (
            DEFAULT_EVENT_IDEMPOTENCY_RETENTION_SECONDS
        ),
        "max_input_upload_bytes": 64 * 1024 * 1024,
        "input_upload_ttl_seconds": 60 * 60,
        "input_resource_retention_seconds": 90 * 24 * 60 * 60,
        "action_job_max_deadline_seconds": 300,
        "action_job_lease_seconds": 330,
        "preview_result_ttl_seconds": 60 * 60,
        "run_artifact_retention_seconds": None,
        "run_artifact_cleanup_batch_size": 100,
        "action_handlers": empty_managed_mapping,
        "artifact_root": None,
        "policy": None,
        "approvals": None,
        "quotas": None,
        "audit": None,
        "attestations": None,
        "require_attestations": False,
        "schedule_clock": None,
        "schedule_parameter_resolver": None,
        "execution_route": "local",
    }
)
MANAGED_BACKEND_SHARED_FIELDS = tuple(MANAGED_BACKEND_DEFAULTS)

_SUPPORTED_ACTIONS = frozenset(
    {
        "connector.test",
        "connector.catalog",
        "connector.schema.inspect",
        "connector.preflight",
        "connector.preview",
        "connector.provision",
        "connector.provision.cleanup",
    }
)


def validate_managed_backend_settings(config: object) -> None:
    """Validate fields shared by headless and HTTP managed configurations."""
    settings = cast(Any, config)
    database_url = settings.database_url
    if database_url is not None and (
        not isinstance(database_url, str) or not database_url.strip()
    ):
        raise ValueError("database_url must be a non-empty SQLAlchemy URL")
    store_id = settings.store_id
    if not isinstance(store_id, str) or not store_id.strip():
        raise ValueError("store_id must be non-empty")
    if not isinstance(settings.engine_options, Mapping):
        raise TypeError("engine_options must be a mapping")
    validate_execution_route(settings.execution_route)

    positive_fields = (
        "event_retention_max_events_per_scope",
        "event_idempotency_retention_seconds",
        "max_input_upload_bytes",
        "input_upload_ttl_seconds",
        "input_resource_retention_seconds",
    )
    for name in positive_fields:
        value = getattr(config, name)
        if type(value) is not int or value < 1:
            raise ValueError(f"{name} must be a positive integer")

    deadline = settings.action_job_max_deadline_seconds
    if type(deadline) is not int or not 1 <= deadline <= 300:
        raise ValueError("action_job_max_deadline_seconds must be between 1 and 300")
    lease = settings.action_job_lease_seconds
    if type(lease) is not int or lease <= deadline:
        raise ValueError("action_job_lease_seconds must exceed the action deadline")
    preview_ttl = settings.preview_result_ttl_seconds
    if (
        type(preview_ttl) is not int
        or not MIN_PREVIEW_RESULT_TTL_SECONDS
        <= preview_ttl
        <= MAX_PREVIEW_RESULT_TTL_SECONDS
    ):
        raise ValueError(
            "preview_result_ttl_seconds must be between "
            f"{MIN_PREVIEW_RESULT_TTL_SECONDS} and "
            f"{MAX_PREVIEW_RESULT_TTL_SECONDS}"
        )
    retention = settings.run_artifact_retention_seconds
    if retention is not None and (type(retention) is not int or retention < 1):
        raise ValueError("run_artifact_retention_seconds must be positive or None")
    batch_size = settings.run_artifact_cleanup_batch_size
    if type(batch_size) is not int or not 1 <= batch_size <= 1000:
        raise ValueError("run_artifact_cleanup_batch_size must be between 1 and 1000")

    handlers_value: object = settings.action_handlers
    if not isinstance(handlers_value, Mapping):
        raise TypeError("action_handlers must be a mapping")
    raw_handlers = cast(Mapping[object, object], handlers_value)
    handlers: dict[str, object] = {}
    unsupported: set[str] = set()
    for action, handler in raw_handlers.items():
        if not isinstance(action, str):
            unsupported.add(str(action))
            continue
        handlers[action] = handler
        if action not in _SUPPORTED_ACTIONS and not (
            action.startswith("connector.catalog.")
            and action.removeprefix("connector.catalog.")
            .replace("-", "")
            .replace("_", "")
            .isalnum()
        ):
            unsupported.add(action)
    if unsupported:
        raise ValueError(
            "action_handlers contains unsupported action(s): "
            + ", ".join(sorted(map(str, unsupported)))
        )
    for action, handler in handlers.items():
        if not callable(handler) or not (
            inspect.iscoroutinefunction(handler)
            or inspect.iscoroutinefunction(type(handler).__call__)
        ):
            raise TypeError(f"action handler {action!r} must be asynchronous")
    resolver = settings.schedule_parameter_resolver
    if resolver is not None and not callable(resolver):
        raise TypeError("schedule_parameter_resolver must be callable or None")
    clock = settings.schedule_clock
    if clock is not None and not (
        callable(clock) or callable(getattr(clock, "now", None))
    ):
        raise TypeError("schedule_clock must be callable or expose now()")


__all__ = [
    "MANAGED_BACKEND_DEFAULTS",
    "MANAGED_BACKEND_SHARED_FIELDS",
    "empty_managed_mapping",
    "validate_managed_backend_settings",
]
