"""Versioned, fail-closed Prefect deployment bindings for managed execution."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
from collections.abc import Callable
from contextlib import suppress
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from etlantic.control_plane import (
    ControlPlaneContext,
    ControlPlaneError,
    ManagedBackend,
)

DEPLOYMENT_SPEC_SCHEMA = "etlantic.prefect.managed_deployment_spec/1"
DEPLOYMENT_BINDING_SCHEMA = "etlantic.prefect.managed_deployment_binding/1"
MANAGED_FLOW_NAME = "etlantic-managed-execution"
MANAGED_FLOW_ENTRYPOINT = "etlantic_prefect.worker.managed_execution_flow"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,47}$")
_ENTRY_POINT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_SPEC_ENV = "ETLANTIC_PREFECT_DEPLOYMENT_SPEC_JSON"
_DEFAULT_DEPLOYMENT_RETENTION_SECONDS = 30 * 24 * 60 * 60


async def _set_deployment_paused(
    client: Any, deployment_id: UUID, *, paused: bool
) -> None:
    """Pause a deployment through the client API available in this Prefect version."""
    operation_name = "pause_deployment" if paused else "resume_deployment"
    operation = getattr(client, operation_name, None)
    if callable(operation):
        await operation(deployment_id)
        return
    setter = getattr(client, "set_deployment_paused_state", None)
    if not callable(setter):
        raise RuntimeError("Prefect client does not support deployment pause state")
    await setter(deployment_id, paused)


def _json_digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _required_text(value: object, name: str, *, maximum: int = 128) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{name} must contain 1 to {maximum} characters")
    if any(ord(char) < 32 for char in value):
        raise ValueError(f"{name} must not contain control characters")
    return value


def _installed_source_fingerprint() -> str:
    """Fingerprint importable source and package manifest files in this wheel."""
    package_root = Path(__file__).resolve().parent
    files = sorted(
        (*package_root.rglob("*.py"), *package_root.rglob("*.json")),
        key=lambda item: item.relative_to(package_root).as_posix(),
    )
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.relative_to(package_root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class ManagedDeploymentSpec:
    """Immutable, secret-free deployment configuration for the Process pool."""

    name: str
    work_pool_name: str
    worker_backend_entry_point: str
    source_sha256: str
    lockfile_sha256: str
    python_version: str
    etlantic_version: str
    etlantic_prefect_version: str
    prefect_version: str
    sqlmodel_version: str
    schema: str = DEPLOYMENT_SPEC_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != DEPLOYMENT_SPEC_SCHEMA:
            raise ValueError("unsupported managed deployment spec schema")
        if _NAME.fullmatch(self.name) is None:
            raise ValueError("deployment name must be a bounded identifier")
        _required_text(self.work_pool_name, "work_pool_name")
        if _ENTRY_POINT.fullmatch(self.worker_backend_entry_point) is None:
            raise ValueError("worker backend must be a bounded entry-point name")
        for field_name in ("source_sha256", "lockfile_sha256"):
            if _SHA256.fullmatch(getattr(self, field_name)) is None:
                raise ValueError(f"{field_name} must be a lowercase SHA-256 value")
        for field_name in (
            "python_version",
            "etlantic_version",
            "etlantic_prefect_version",
            "prefect_version",
            "sqlmodel_version",
        ):
            value = _required_text(getattr(self, field_name), field_name, maximum=64)
            if any(char.isspace() for char in value):
                raise ValueError(f"{field_name} must not contain whitespace")

    @classmethod
    def from_current_runtime(
        cls,
        *,
        name: str,
        work_pool_name: str,
        worker_backend_entry_point: str,
        source_sha256: str | None = None,
        lockfile_sha256: str,
    ) -> ManagedDeploymentSpec:
        """Capture exact runtime package versions alongside build fingerprints."""
        installed_source = _installed_source_fingerprint()
        if source_sha256 is not None and source_sha256 != installed_source:
            raise ValueError(
                "source_sha256 does not match the installed etlantic-prefect package"
            )
        try:
            versions = {
                package: version(package)
                for package in (
                    "etlantic",
                    "etlantic-prefect",
                    "prefect",
                    "etlantic-sqlmodel",
                )
            }
        except PackageNotFoundError as exc:
            raise RuntimeError(
                "managed deployment requires installed ETLantic, Prefect, and SQLModel packages"
            ) from exc
        return cls(
            name=name,
            work_pool_name=work_pool_name,
            worker_backend_entry_point=worker_backend_entry_point,
            source_sha256=installed_source,
            lockfile_sha256=lockfile_sha256,
            python_version=platform.python_version(),
            etlantic_version=versions["etlantic"],
            etlantic_prefect_version=versions["etlantic-prefect"],
            prefect_version=versions["prefect"],
            sqlmodel_version=versions["etlantic-sqlmodel"],
        )

    @property
    def fingerprint(self) -> str:
        return _json_digest(asdict(self))

    @property
    def deployment_name(self) -> str:
        return f"{self.name}--{self.fingerprint[:16]}"

    @property
    def tags(self) -> tuple[str, ...]:
        return (
            "etlantic-managed/1",
            f"etlantic-spec:{self.fingerprint}",
            f"etlantic-source:{self.source_sha256}",
            f"etlantic-lock:{self.lockfile_sha256}",
        )

    def to_dict(self) -> dict[str, str]:
        return {**asdict(self), "fingerprint": self.fingerprint}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ManagedDeploymentSpec:
        expected = {
            "schema",
            "name",
            "work_pool_name",
            "worker_backend_entry_point",
            "source_sha256",
            "lockfile_sha256",
            "python_version",
            "etlantic_version",
            "etlantic_prefect_version",
            "prefect_version",
            "sqlmodel_version",
            "fingerprint",
        }
        if set(value) != expected:
            raise ValueError("managed deployment spec has unknown or missing fields")
        raw = {key: value[key] for key in expected - {"fingerprint"}}
        if not all(isinstance(item, str) for item in raw.values()):
            raise ValueError("managed deployment spec fields must be strings")
        spec = cls(**raw)
        if value["fingerprint"] != spec.fingerprint:
            raise ValueError("managed deployment spec fingerprint does not match")
        return spec

    def assert_local_runtime(self) -> None:
        """Fail before effects when installed runtime versions drift from the spec."""
        try:
            actual = {
                "python_version": platform.python_version(),
                "etlantic_version": version("etlantic"),
                "etlantic_prefect_version": version("etlantic-prefect"),
                "prefect_version": version("prefect"),
                "sqlmodel_version": version("etlantic-sqlmodel"),
            }
        except PackageNotFoundError as exc:
            raise RuntimeError("managed worker runtime is incomplete") from exc
        expected = {
            "python_version": self.python_version,
            "etlantic_version": self.etlantic_version,
            "etlantic_prefect_version": self.etlantic_prefect_version,
            "prefect_version": self.prefect_version,
            "sqlmodel_version": self.sqlmodel_version,
        }
        if actual != expected:
            raise RuntimeError(
                "managed worker runtime does not match its deployment spec"
            )
        if _installed_source_fingerprint() != self.source_sha256:
            raise RuntimeError(
                "managed worker source does not match its deployment spec"
            )


@dataclass(frozen=True, slots=True)
class ManagedDeploymentBinding:
    """The Prefect deployment ID cryptographically bound to one immutable spec."""

    spec: ManagedDeploymentSpec
    deployment_id: UUID
    schema: str = DEPLOYMENT_BINDING_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != DEPLOYMENT_BINDING_SCHEMA:
            raise ValueError("unsupported managed deployment binding schema")
        object.__setattr__(self, "deployment_id", UUID(str(self.deployment_id)))

    @property
    def fingerprint(self) -> str:
        return _json_digest(
            {
                "schema": self.schema,
                "deployment_id": str(self.deployment_id),
                "spec_fingerprint": self.spec.fingerprint,
            }
        )

    @property
    def execution_route(self) -> str:
        return f"prefect:{self.fingerprint}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "deployment_id": str(self.deployment_id),
            "spec": self.spec.to_dict(),
            "fingerprint": self.fingerprint,
            "execution_route": self.execution_route,
        }

    def to_environment(self) -> dict[str, str]:
        return {
            "ETLANTIC_PREFECT_DEPLOYMENT_ID": str(self.deployment_id),
            "ETLANTIC_PREFECT_ROUTE_ID": self.execution_route,
            "ETLANTIC_PREFECT_WORKER_BACKEND": self.spec.worker_backend_entry_point,
            _SPEC_ENV: json.dumps(
                self.spec.to_dict(),
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ManagedDeploymentBinding:
        if set(value) != {
            "schema",
            "deployment_id",
            "spec",
            "fingerprint",
            "execution_route",
        }:
            raise ValueError("managed deployment binding has unknown or missing fields")
        if not isinstance(value["schema"], str) or not isinstance(
            value["deployment_id"], str
        ):
            raise ValueError("managed deployment binding fields are invalid")
        if not isinstance(value["spec"], dict):
            raise ValueError("managed deployment binding spec is invalid")
        binding = cls(
            schema=value["schema"],
            deployment_id=UUID(value["deployment_id"]),
            spec=ManagedDeploymentSpec.from_dict(cast(dict[str, Any], value["spec"])),
        )
        if (
            value["fingerprint"] != binding.fingerprint
            or value["execution_route"] != binding.execution_route
        ):
            raise ValueError("managed deployment binding fingerprint does not match")
        return binding

    @classmethod
    def from_environment(
        cls, environment: dict[str, str] | None = None
    ) -> ManagedDeploymentBinding:
        values = os.environ if environment is None else environment
        try:
            deployment_id = values["ETLANTIC_PREFECT_DEPLOYMENT_ID"]
            route = values["ETLANTIC_PREFECT_ROUTE_ID"]
            backend = values["ETLANTIC_PREFECT_WORKER_BACKEND"]
            spec_json = values[_SPEC_ENV]
            raw_spec = json.loads(spec_json)
        except (KeyError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                "trusted Prefect deployment binding is missing or invalid"
            ) from exc
        if not isinstance(raw_spec, dict):
            raise RuntimeError("trusted Prefect deployment spec is invalid")
        binding = cls(
            spec=ManagedDeploymentSpec.from_dict(cast(dict[str, Any], raw_spec)),
            deployment_id=UUID(deployment_id),
        )
        if (
            route != binding.execution_route
            or backend != binding.spec.worker_backend_entry_point
        ):
            raise RuntimeError("trusted Prefect deployment binding is inconsistent")
        binding.spec.assert_local_runtime()
        return binding

    def verify_remote_deployment(
        self,
        deployment: Any,
        *,
        require_worker_environment: bool = True,
        require_active: bool = True,
    ) -> bool:
        """Reject missing or drifted remote configuration before ETL effects."""
        tags = set(getattr(deployment, "tags", None) or ())
        job_variables = dict(getattr(deployment, "job_variables", None) or {})
        expected_job_variables = {"env": self.to_environment()}
        if job_variables == expected_job_variables:
            environment_ready = True
        elif not job_variables and not require_worker_environment:
            environment_ready = False
        else:
            environment_ready = False
        if (
            UUID(str(getattr(deployment, "id", ""))) != self.deployment_id
            or getattr(deployment, "name", None) != self.spec.deployment_name
            or getattr(deployment, "version", None) != self.spec.fingerprint
            or getattr(deployment, "work_pool_name", None) != self.spec.work_pool_name
            or getattr(deployment, "entrypoint", None) != MANAGED_FLOW_ENTRYPOINT
            or getattr(deployment, "path", None) is not None
            or dict(getattr(deployment, "parameters", None) or {}) != {}
            or getattr(deployment, "enforce_parameter_schema", None) is not True
            or (require_active and getattr(deployment, "paused", None) is not False)
            or (require_worker_environment and not environment_ready)
            or (
                not require_worker_environment
                and job_variables not in ({}, expected_job_variables)
            )
            or bool(getattr(deployment, "schedules", None))
            or not set(self.spec.tags).issubset(tags)
        ):
            raise RuntimeError("Prefect deployment does not match its accepted binding")
        from etlantic_prefect.worker import managed_execution_flow

        expected_parameter_schema = managed_execution_flow.parameters.model_dump(
            mode="json", exclude_unset=True
        )
        if (
            getattr(deployment, "parameter_openapi_schema", None)
            != expected_parameter_schema
        ):
            raise RuntimeError("Prefect deployment parameter schema has drifted")
        return environment_ready

    @staticmethod
    def verify_remote_work_pool(work_pool: Any) -> None:
        """Reject infrastructure changes outside the qualified Process pool."""
        pool_type = getattr(
            getattr(work_pool, "type", None), "value", getattr(work_pool, "type", None)
        )
        if pool_type != "process":
            raise RuntimeError("managed Prefect execution requires a Process work pool")


class PrefectDeploymentRegistrar:
    """Read-only preview and explicit, immutable registration for Process pools."""

    def __init__(self, client_factory: Callable[[], Any] | None = None) -> None:
        self._client_factory = client_factory

    def _get_client(self) -> Any:
        if self._client_factory is not None:
            return self._client_factory()
        from prefect.client.orchestration import get_client

        return get_client()

    async def preview(self, spec: ManagedDeploymentSpec) -> dict[str, Any]:
        """Inspect the Process pool and any immutable-version collision."""
        async with self._get_client() as client:
            return await self._preview(client, spec)

    async def _preview(
        self, client: Any, spec: ManagedDeploymentSpec
    ) -> dict[str, Any]:
        pool = await client.read_work_pool(spec.work_pool_name)
        ManagedDeploymentBinding.verify_remote_work_pool(pool)
        existing: Any | None = None
        from prefect.exceptions import ObjectNotFound

        with suppress(ObjectNotFound):
            existing = await client.read_deployment_by_name(
                f"{MANAGED_FLOW_NAME}/{spec.deployment_name}"
            )
        binding: ManagedDeploymentBinding | None = None
        binding_ready = False
        job_variables: dict[str, Any] = {}
        paused: bool | None = None
        if existing is not None:
            binding = ManagedDeploymentBinding(spec, UUID(str(existing.id)))
            job_variables = dict(getattr(existing, "job_variables", None) or {})
            paused_value = getattr(existing, "paused", None)
            paused = paused_value if isinstance(paused_value, bool) else None
            binding_ready = binding.verify_remote_deployment(
                existing,
                require_worker_environment=False,
                require_active=False,
            )
        return {
            "spec": spec.to_dict(),
            "deployment_name": spec.deployment_name,
            "deployment_exists": existing is not None,
            "deployment_id": str(existing.id) if existing is not None else None,
            "execution_route": binding.execution_route if binding is not None else None,
            "binding_ready": binding_ready,
            "paused": paused,
            "work_pool_type": "process",
            "schedules": [],
            "default_parameters": {},
            "job_variables": sorted(job_variables),
            "environment_variables": sorted(
                str(name) for name in dict(job_variables.get("env", {}) or {})
            ),
        }

    async def register(
        self,
        spec: ManagedDeploymentSpec,
        *,
        expected_fingerprint: str,
    ) -> ManagedDeploymentBinding:
        """Create one versioned deployment after explicit preview confirmation."""
        spec.assert_local_runtime()
        if expected_fingerprint != spec.fingerprint:
            raise ValueError(
                "deployment preview fingerprint changed; review before registration"
            )
        async with self._get_client() as client:
            preview = await self._preview(client, spec)
            if preview["deployment_exists"]:
                binding = ManagedDeploymentBinding(
                    spec=spec,
                    deployment_id=UUID(str(preview["deployment_id"])),
                )
                if not preview["binding_ready"]:
                    from prefect.client.schemas.actions import DeploymentUpdate

                    await client.update_deployment(
                        binding.deployment_id,
                        DeploymentUpdate(
                            job_variables={"env": binding.to_environment()}
                        ),
                    )
                remote = await client.read_deployment(binding.deployment_id)
                binding.verify_remote_deployment(remote, require_active=False)
                await _set_deployment_paused(
                    client, binding.deployment_id, paused=False
                )
                remote = await client.read_deployment(binding.deployment_id)
                binding.verify_remote_deployment(remote)
                return binding
            from etlantic_prefect.worker import managed_execution_flow

            flow_id = await client.create_flow_from_name(managed_execution_flow.name)
            parameter_schema = managed_execution_flow.parameters.model_dump(
                mode="json", exclude_unset=True
            )
            deployment_id = await client.create_deployment(
                flow_id=flow_id,
                name=spec.deployment_name,
                version=spec.fingerprint,
                schedules=[],
                parameters={},
                description=(
                    "ETLantic managed execution; parameters contain only a bounded "
                    "reference to previously accepted work."
                ),
                work_pool_name=spec.work_pool_name,
                tags=list(spec.tags),
                path=None,
                entrypoint=MANAGED_FLOW_ENTRYPOINT,
                paused=True,
                parameter_openapi_schema=parameter_schema,
                enforce_parameter_schema=True,
                job_variables={},
                pull_steps=[],
            )
            binding = ManagedDeploymentBinding(
                spec=spec,
                deployment_id=UUID(str(deployment_id)),
            )
            remote = await client.read_deployment(binding.deployment_id)
            binding.verify_remote_deployment(
                remote,
                require_worker_environment=False,
                require_active=False,
            )
            from prefect.client.schemas.actions import DeploymentUpdate

            await client.update_deployment(
                binding.deployment_id,
                DeploymentUpdate(job_variables={"env": binding.to_environment()}),
            )
            remote = await client.read_deployment(binding.deployment_id)
            binding.verify_remote_deployment(remote, require_active=False)
            await _set_deployment_paused(client, binding.deployment_id, paused=False)
            remote = await client.read_deployment(binding.deployment_id)
            binding.verify_remote_deployment(remote)
            return binding

    async def retire(
        self,
        binding: ManagedDeploymentBinding,
        *,
        backend: ManagedBackend,
        context: ControlPlaneContext,
        expected_fingerprint: str,
    ) -> dict[str, Any]:
        """Stop admissions, drain canonical and remote work, then retain paused.

        Retired deployments are deliberately retained for audit and rollback.
        This operation never deletes Prefect history or the executable binding.
        """
        if expected_fingerprint != binding.fingerprint:
            raise ValueError("deployment retirement fingerprint changed")
        service = getattr(backend, "managed_service", None)
        if service is None:
            raise TypeError("route retirement requires a ManagedBackend")
        lifecycle = service.get_execution_route_lifecycle(
            context, binding.execution_route
        )
        if lifecycle["status"] in {"cleanup_pending", "cleaned"}:
            raise ControlPlaneError.conflict(
                "Execution route cleanup has started and cannot be retired again",
                extensions={"reason": "execution_route_cleanup_started"},
            )
        if lifecycle["status"] == "active":
            try:
                lifecycle = service.transition_execution_route_lifecycle(
                    context,
                    binding.execution_route,
                    expected_revision=lifecycle["revision"],
                    status="draining",
                )
            except ControlPlaneError as exc:
                if exc.extensions.get("reason") != "stale_route_revision":
                    raise
                lifecycle = service.get_execution_route_lifecycle(
                    context, binding.execution_route
                )
                if lifecycle["status"] not in {"draining", "retired"}:
                    raise
        if lifecycle["status"] == "retired":
            async with self._get_client() as client:
                remote = await client.read_deployment(binding.deployment_id)
                binding.verify_remote_deployment(remote, require_active=False)
                pool = await client.read_work_pool(binding.spec.work_pool_name)
                binding.verify_remote_work_pool(pool)
                if getattr(remote, "paused", None) is not True:
                    await _set_deployment_paused(
                        client, binding.deployment_id, paused=True
                    )
                if await self._has_active_deployment_runs(client, binding):
                    return {
                        **lifecycle,
                        "deployment_id": str(binding.deployment_id),
                        "deployment_paused": True,
                        "deployment_retained": True,
                        "reason": "remote_flow_runs_remain",
                    }
            return {
                **lifecycle,
                "deployment_id": str(binding.deployment_id),
                "deployment_paused": True,
                "deployment_retained": True,
                "reason": None,
            }

        workload = lifecycle["workload"]
        if lifecycle.get("references", {}).get("schedule_reservations", 0):
            return {
                **lifecycle,
                "deployment_id": str(binding.deployment_id),
                "deployment_paused": False,
                "deployment_retained": True,
                "reason": "schedule_references_remain",
            }
        if not workload["drained"]:
            return {
                **lifecycle,
                "deployment_id": str(binding.deployment_id),
                "deployment_paused": False,
                "deployment_retained": True,
                "reason": "canonical_work_remains",
            }

        async with self._get_client() as client:
            remote = await client.read_deployment(binding.deployment_id)
            binding.verify_remote_deployment(remote, require_active=False)
            pool = await client.read_work_pool(binding.spec.work_pool_name)
            binding.verify_remote_work_pool(pool)
            if await self._has_active_deployment_runs(client, binding):
                return {
                    **lifecycle,
                    "deployment_id": str(binding.deployment_id),
                    "deployment_paused": False,
                    "deployment_retained": True,
                    "reason": "remote_flow_runs_remain",
                }
            if getattr(remote, "paused", None) is not True:
                await _set_deployment_paused(client, binding.deployment_id, paused=True)
            remote = await client.read_deployment(binding.deployment_id)
            binding.verify_remote_deployment(remote, require_active=False)
            if await self._has_active_deployment_runs(client, binding):
                return {
                    **lifecycle,
                    "deployment_id": str(binding.deployment_id),
                    "deployment_paused": True,
                    "deployment_retained": True,
                    "reason": "remote_flow_runs_remain",
                }

        try:
            retired = service.transition_execution_route_lifecycle(
                context,
                binding.execution_route,
                expected_revision=lifecycle["revision"],
                status="retired",
            )
        except ControlPlaneError as exc:
            if exc.extensions.get("reason") != "stale_route_revision":
                raise
            current = service.get_execution_route_lifecycle(
                context, binding.execution_route
            )
            if current["status"] != "retired":
                raise
            # Concurrent retirement may win after this process pauses and
            # verifies the same immutable deployment. Re-enter the idempotent
            # retired path to confirm the retained remote binding and drain.
            return await self.retire(
                binding,
                backend=backend,
                context=context,
                expected_fingerprint=expected_fingerprint,
            )
        return {
            **retired,
            "deployment_id": str(binding.deployment_id),
            "deployment_paused": True,
            "deployment_retained": True,
            "reason": None,
        }

    async def reactivate(
        self,
        binding: ManagedDeploymentBinding,
        *,
        backend: ManagedBackend,
        context: ControlPlaneContext,
        expected_fingerprint: str,
    ) -> dict[str, Any]:
        """Verify and resume the retained binding before reopening admissions."""
        if expected_fingerprint != binding.fingerprint:
            raise ValueError("deployment reactivation fingerprint changed")
        service = getattr(backend, "managed_service", None)
        if service is None:
            raise TypeError("route reactivation requires a ManagedBackend")
        lifecycle = service.get_execution_route_lifecycle(
            context, binding.execution_route
        )
        if lifecycle["status"] in {"cleanup_pending", "cleaned"}:
            raise ControlPlaneError.conflict(
                "Execution route cleanup has started and cannot be reactivated",
                extensions={"reason": "execution_route_cleanup_started"},
            )
        async with self._get_client() as client:
            deployment = await client.read_deployment(binding.deployment_id)
            binding.verify_remote_deployment(deployment, require_active=False)
            pool = await client.read_work_pool(binding.spec.work_pool_name)
            binding.verify_remote_work_pool(pool)
            if getattr(deployment, "paused", None) is True:
                await _set_deployment_paused(
                    client, binding.deployment_id, paused=False
                )
            deployment = await client.read_deployment(binding.deployment_id)
            binding.verify_remote_deployment(deployment)
        if lifecycle["status"] == "active":
            return {**lifecycle, "deployment_id": str(binding.deployment_id)}
        active = service.transition_execution_route_lifecycle(
            context,
            binding.execution_route,
            expected_revision=lifecycle["revision"],
            status="active",
        )
        return {**active, "deployment_id": str(binding.deployment_id)}

    async def cleanup(
        self,
        binding: ManagedDeploymentBinding,
        *,
        backend: ManagedBackend,
        context: ControlPlaneContext,
        expected_fingerprint: str,
        minimum_retention_seconds: int = _DEFAULT_DEPLOYMENT_RETENTION_SECONDS,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Delete one unused retired deployment after a durable cleanup fence.

        Prefect flow-run history is retained. Any canonical submission, live
        schedule, reservation, or historical remote run makes this deployment
        ineligible. Once cleanup is pending, reactivation is permanently
        fenced; a retry safely finishes a delete whose response was lost.
        """
        if expected_fingerprint != binding.fingerprint:
            raise ValueError("deployment cleanup fingerprint changed")
        if type(minimum_retention_seconds) is not int or minimum_retention_seconds < 0:
            raise ValueError("minimum_retention_seconds must be a non-negative integer")
        service = getattr(backend, "managed_service", None)
        if service is None:
            raise TypeError("route cleanup requires a ManagedBackend")
        schedule_store = getattr(backend, "schedule_store", None)
        count_schedules = getattr(
            schedule_store, "execution_route_reference_count", None
        )
        if not callable(count_schedules):
            raise TypeError(
                "route cleanup requires a store-wide schedule reference scan"
            )

        lifecycle = service.get_execution_route_lifecycle(
            context, binding.execution_route
        )
        if lifecycle["status"] == "cleaned":
            return {
                **lifecycle,
                "deployment_id": str(binding.deployment_id),
                "deployment_deleted": True,
                "deployment_retained": False,
                "reason": None,
            }
        if lifecycle["status"] not in {"retired", "cleanup_pending"}:
            raise ControlPlaneError.conflict(
                "Only a retired deployment can be cleaned up",
                extensions={"reason": "execution_route_not_retired"},
            )
        if lifecycle["status"] == "retired":
            changed_at = lifecycle.get("changed_at")
            if not isinstance(changed_at, str):
                raise ControlPlaneError.conflict(
                    "Retired route has no retention timestamp",
                    extensions={"reason": "execution_route_retention_unknown"},
                )
            retired_at = datetime.fromisoformat(changed_at.replace("Z", "+00:00"))
            current_time = now or datetime.now(UTC)
            if (
                current_time.tzinfo is None
                or current_time.utcoffset() is None
                or retired_at.tzinfo is None
                or retired_at.utcoffset() is None
            ):
                raise ValueError("cleanup timestamps must be timezone-aware")
            if (current_time - retired_at).total_seconds() < minimum_retention_seconds:
                return {
                    **lifecycle,
                    "deployment_id": str(binding.deployment_id),
                    "deployment_deleted": False,
                    "deployment_retained": True,
                    "reason": "retention_period_not_elapsed",
                }

        def references_clear(snapshot: dict[str, Any]) -> bool:
            references = snapshot.get("references")
            workload = snapshot.get("workload")
            return (
                isinstance(references, dict)
                and not any(int(value) for value in references.values())
                and isinstance(workload, dict)
                and workload.get("drained") is True
                and int(count_schedules(binding.execution_route)) == 0
            )

        if not references_clear(lifecycle):
            return {
                **lifecycle,
                "deployment_id": str(binding.deployment_id),
                "deployment_deleted": False,
                "deployment_retained": True,
                "reason": "route_references_remain",
            }

        from prefect.exceptions import ObjectNotFound

        async def verify_unused_paused_deployment(client: Any) -> bool:
            """Return false only when the exact deployment no longer exists."""
            try:
                remote = await client.read_deployment(binding.deployment_id)
            except ObjectNotFound:
                return False
            binding.verify_remote_deployment(remote, require_active=False)
            pool = await client.read_work_pool(binding.spec.work_pool_name)
            binding.verify_remote_work_pool(pool)
            if getattr(remote, "paused", None) is not True:
                await _set_deployment_paused(client, binding.deployment_id, paused=True)
                remote = await client.read_deployment(binding.deployment_id)
                binding.verify_remote_deployment(remote, require_active=False)
            if getattr(remote, "paused", None) is not True:
                raise RuntimeError("retired deployment could not be paused")
            return True

        async with self._get_client() as client:
            exists = await verify_unused_paused_deployment(client)
            if await self._has_any_deployment_runs(client, binding):
                return {
                    **lifecycle,
                    "deployment_id": str(binding.deployment_id),
                    "deployment_deleted": False,
                    "deployment_retained": True,
                    "reason": "remote_flow_run_history_remains",
                }
        if lifecycle["status"] == "retired":
            try:
                lifecycle = service.transition_execution_route_lifecycle(
                    context,
                    binding.execution_route,
                    expected_revision=lifecycle["revision"],
                    status="cleanup_pending",
                )
            except ControlPlaneError as exc:
                if exc.extensions.get("reason") != "stale_route_revision":
                    raise
                lifecycle = service.get_execution_route_lifecycle(
                    context, binding.execution_route
                )
                if lifecycle["status"] not in {"cleanup_pending", "cleaned"}:
                    raise
        if lifecycle["status"] == "cleaned":
            return {
                **lifecycle,
                "deployment_id": str(binding.deployment_id),
                "deployment_deleted": True,
                "deployment_retained": False,
                "reason": None,
            }
        if not references_clear(lifecycle):
            return {
                **lifecycle,
                "deployment_id": str(binding.deployment_id),
                "deployment_deleted": False,
                "deployment_retained": True,
                "reason": "route_references_remain",
            }

        async with self._get_client() as client:
            exists = await verify_unused_paused_deployment(client)
            if await self._has_any_deployment_runs(client, binding):
                return {
                    **lifecycle,
                    "deployment_id": str(binding.deployment_id),
                    "deployment_deleted": False,
                    "deployment_retained": True,
                    "reason": "remote_flow_run_history_remains",
                }
            if exists:
                # Another cleanup owner may have completed the same exact
                # delete while this caller was waiting on the API.
                with suppress(ObjectNotFound):
                    await client.delete_deployment(binding.deployment_id)
        try:
            cleaned = service.transition_execution_route_lifecycle(
                context,
                binding.execution_route,
                expected_revision=lifecycle["revision"],
                status="cleaned",
            )
        except ControlPlaneError as exc:
            if exc.extensions.get("reason") != "stale_route_revision":
                raise
            cleaned = service.get_execution_route_lifecycle(
                context, binding.execution_route
            )
            if cleaned["status"] != "cleaned":
                raise
        return {
            **cleaned,
            "deployment_id": str(binding.deployment_id),
            "deployment_deleted": True,
            "deployment_retained": False,
            "reason": None,
        }

    @staticmethod
    async def _has_any_deployment_runs(client: Any, binding: Any) -> bool:
        """Keep a deployment if any Prefect flow-run history still points to it."""
        from prefect.client.schemas.filters import (
            FlowRunFilter,
            FlowRunFilterDeploymentId,
        )

        runs = await client.read_flow_runs(
            flow_run_filter=FlowRunFilter(
                deployment_id=FlowRunFilterDeploymentId(any_=[binding.deployment_id])
            ),
            limit=1,
        )
        return bool(runs)

    @staticmethod
    async def _has_active_deployment_runs(
        client: Any, binding: ManagedDeploymentBinding
    ) -> bool:
        """Bound the retirement check to the first nonterminal remote run."""
        from prefect.client.schemas.filters import (
            FlowRunFilter,
            FlowRunFilterDeploymentId,
            FlowRunFilterState,
            FlowRunFilterStateType,
        )
        from prefect.client.schemas.objects import StateType

        active_states = [
            StateType.SCHEDULED,
            StateType.PENDING,
            StateType.RUNNING,
            StateType.CANCELLING,
            StateType.PAUSED,
        ]
        runs = await client.read_flow_runs(
            flow_run_filter=FlowRunFilter(
                deployment_id=FlowRunFilterDeploymentId(any_=[binding.deployment_id]),
                state=FlowRunFilterState(
                    type=FlowRunFilterStateType(any_=active_states)
                ),
            ),
            limit=1,
        )
        return bool(runs)


__all__ = [
    "DEPLOYMENT_BINDING_SCHEMA",
    "DEPLOYMENT_SPEC_SCHEMA",
    "ManagedDeploymentBinding",
    "ManagedDeploymentSpec",
    "PrefectDeploymentRegistrar",
]
