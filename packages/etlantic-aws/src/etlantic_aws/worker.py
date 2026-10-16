"""Installed Fargate worker for one immutable accepted execution reference."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from collections.abc import Iterable, Mapping
from importlib.metadata import EntryPoint, entry_points
from typing import Any, cast
from urllib.parse import urlsplit

from etlantic.control_plane import (
    AcceptedExecutionReference,
    ControlPlaneContext,
    ManagedBackend,
    validate_control_plane_context,
)

from etlantic_aws.binding import ECSExecutionBinding

_ENTRY_POINT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_METADATA_HOST = "169.254.170.2"
_MAX_METADATA_BYTES = 65_536


def _mapping_rows(value: object) -> list[Mapping[str, Any]] | None:
    if not isinstance(value, list) or any(
        not isinstance(item, Mapping) for item in cast(Iterable[object], value)
    ):
        return None
    return [cast(Mapping[str, Any], item) for item in cast(Iterable[object], value)]


def read_task_metadata(*, opener: Any = None) -> Mapping[str, Any]:
    """Read the ECS v4 task endpoint without honoring proxy environment vars."""
    base = os.environ.get("ECS_CONTAINER_METADATA_URI_V4")
    if base is None:
        raise RuntimeError("trusted ECS task metadata endpoint is unavailable")
    parsed = urlsplit(base)
    if (
        parsed.scheme != "http"
        or parsed.hostname != _METADATA_HOST
        or parsed.port not in (None, 80)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeError("trusted ECS task metadata endpoint is unavailable")
    url = base.rstrip("/") + "/task"
    if opener is None:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({})).open
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        response = opener(request, timeout=2.0)
        with response:
            raw = response.read(_MAX_METADATA_BYTES + 1)
    except Exception:
        raise RuntimeError("ECS task metadata could not be read") from None
    if len(raw) > _MAX_METADATA_BYTES:
        raise RuntimeError("ECS task metadata exceeded its size limit")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        raise RuntimeError("ECS task metadata is malformed") from None
    if not isinstance(value, Mapping):
        raise RuntimeError("ECS task metadata is malformed")
    return cast(Mapping[str, Any], value)


class ECSWorker:
    """Verify ECS task identity and execute only its matching accepted work."""

    def __init__(
        self,
        backend: ManagedBackend,
        context: ControlPlaneContext,
        binding: ECSExecutionBinding,
    ) -> None:
        validate_control_plane_context(context)
        configured_route = getattr(backend.managed_service, "execution_route", None)
        if configured_route != binding.execution_route:
            raise ValueError("managed backend route does not match the ECS binding")
        self.backend = backend
        self.context = context
        self.binding = binding

    def execute(
        self,
        reference_value: Mapping[str, Any],
        *,
        metadata: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        reference = AcceptedExecutionReference.from_dict(reference_value)
        self._verify_task_metadata(metadata)
        durable = self.backend.durable_work
        submission = durable.get_submission(self.context, reference.submission_id)
        canonical_reference = AcceptedExecutionReference.from_submission(submission)
        if canonical_reference != reference:
            raise RuntimeError("task reference does not match accepted work")
        if submission.execution_route != self.binding.execution_route:
            raise RuntimeError("accepted work is assigned to another execution route")
        dispatch = durable.get_dispatch(self.context, reference.submission_id)
        if (
            dispatch.backend_kind != "ecs"
            or dispatch.execution_route != self.binding.execution_route
            or dispatch.binding_fingerprint != self.binding.fingerprint
            or dispatch.plan_fingerprint != reference.plan_fingerprint
            or dispatch.envelope_sha256 != reference.envelope_sha256
            or dispatch.status not in {"leased", "uncertain", "dispatched"}
            or (
                dispatch.status == "dispatched"
                and dispatch.remote_run_id is not None
                and dispatch.remote_run_id != metadata.get("TaskARN")
            )
        ):
            raise RuntimeError("durable ECS dispatch does not match this task")
        result = self.backend.execute_submission(
            self.context,
            reference.submission_id,
            owner_id=f"ecs:{metadata['TaskARN']}",
            execution_route=self.binding.execution_route,
        )
        return {
            "submission_id": reference.submission_id,
            "status": result.get("status"),
            "executed": result.get("executed") is True,
            "report_sha256": result.get("report_sha256"),
            "attempt_id": result.get("attempt_id"),
        }

    def _verify_task_metadata(self, metadata: Mapping[str, Any]) -> None:
        task_arn = metadata.get("TaskARN")
        task_prefix = (
            f"arn:{self.binding.partition}:ecs:{self.binding.region}:"
            f"{self.binding.account_id}:task/"
        )
        if not isinstance(task_arn, str) or not task_arn.startswith(task_prefix):
            raise RuntimeError("runtime task identity does not match the ECS binding")
        cluster_name = self.binding.cluster_arn.rsplit("/", 1)[-1]
        if metadata.get("Cluster") not in {self.binding.cluster_arn, cluster_name}:
            raise RuntimeError("runtime task cluster does not match the ECS binding")
        task_family = self.binding.task_definition_arn.rsplit("/", 1)[1].rsplit(":", 1)[
            0
        ]
        if metadata.get("Family") != task_family:
            raise RuntimeError(
                "runtime task definition family does not match the binding"
            )
        if (
            str(metadata.get("Revision"))
            != self.binding.task_definition_arn.rsplit(":", 1)[1]
        ):
            raise RuntimeError(
                "runtime task definition revision does not match the binding"
            )
        containers = _mapping_rows(metadata.get("Containers"))
        expected_image, expected_digest = self.binding.image_digest.split("@", 1)
        if containers is None or not any(
            item.get("Name") == self.binding.container_name
            and item.get("Image") in (self.binding.image_digest, expected_image)
            and isinstance(item.get("ImageID"), str)
            and item.get("ImageID", "").endswith(expected_digest)
            for item in containers
        ):
            raise RuntimeError(
                "runtime container image does not match the pinned digest"
            )


def load_trusted_backend(name: str) -> tuple[ManagedBackend, ControlPlaneContext]:
    """Load exactly one installed backend factory from the ECS worker group."""
    if _ENTRY_POINT.fullmatch(name) is None:
        raise RuntimeError("trusted ECS worker backend is not configured")
    matches: tuple[EntryPoint, ...] = tuple(
        entry_points(group="etlantic.ecs_worker_backends", name=name)
    )
    if len(matches) != 1:
        raise RuntimeError("configured ECS worker backend is unavailable or ambiguous")
    factory = matches[0].load()
    if not callable(factory):
        raise RuntimeError("configured ECS worker backend factory is invalid")
    raw_result: object = factory()
    if not isinstance(raw_result, tuple):
        raise RuntimeError("worker factory returned an invalid backend context")
    factory_result = cast(tuple[object, ...], raw_result)
    if len(factory_result) != 2:
        raise RuntimeError("worker factory returned an invalid backend context")
    backend_value, context_value = factory_result
    if not isinstance(backend_value, ManagedBackend) or not isinstance(
        context_value, ControlPlaneContext
    ):
        raise RuntimeError("worker factory returned an invalid backend context")
    backend = backend_value
    context = context_value
    validate_control_plane_context(context)
    return backend, context


def main() -> int:
    """Execute the one reference passed by the trusted RunTask adapter."""
    try:
        binding_json = os.environ["ETLANTIC_ECS_BINDING_JSON"]
        reference_json = os.environ["ETLANTIC_ACCEPTED_REFERENCE_JSON"]
        backend_name = os.environ["ETLANTIC_ECS_WORKER_BACKEND"]
        binding_value: object = json.loads(binding_json)
        reference_value: object = json.loads(reference_json)
        if not isinstance(binding_value, Mapping) or not isinstance(
            reference_value, Mapping
        ):
            raise RuntimeError("worker configuration is malformed")
        binding = ECSExecutionBinding.from_dict(cast(Mapping[str, Any], binding_value))
        backend, context = load_trusted_backend(backend_name)
        try:
            result = ECSWorker(backend, context, binding).execute(
                cast(Mapping[str, Any], reference_value),
                metadata=read_task_metadata(),
            )
            sys.stdout.write(
                json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n"
            )
            return 0 if result.get("status") in {"completed", "cancelled"} else 1
        finally:
            backend.close()
    except Exception:
        # Do not print exception text or provider payloads into retained logs.
        sys.stderr.write(
            "ETLantic ECS worker failed; inspect protected canonical diagnostics.\n"
        )
        return 1


__all__ = ["ECSWorker", "load_trusted_backend", "main", "read_task_metadata"]
