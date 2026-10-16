"""Posit Connect schedule operations with an explicit experimental API gate."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable, Mapping
from contextlib import suppress
from copy import copy, deepcopy
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal, Protocol, cast
from urllib.parse import urlsplit

from etlantic.control_plane.models import ControlPlaneContext
from etlantic.control_plane.schedule_models import ScheduleRecord, ScheduleSpec
from etlantic.service.schedule import ScheduleApplicationService

if TYPE_CHECKING:
    from etlantic_rsconnect.bundle import TriggerBundle
    from etlantic_rsconnect.deployment import DeploymentResult, RsconnectPythonDeployer

CONNECT_SCHEDULE_API_PREVIEW = "posit-connect-schedule-api/experimental"
_CONTENT_GUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


class ScheduleOperationError(RuntimeError):
    """A schedule operation failed before a remote mutation was attempted."""


class ScheduleOperationUnknown(ScheduleOperationError):
    """A remote mutation may have committed; reconcile before retrying."""


@dataclass(frozen=True, slots=True)
class ConnectCapabilityReport:
    """Observed API support; installation alone never implies qualification."""

    server_url: str
    server_version: str | None
    schedule_api: Literal["experimental", "unavailable"]
    create: bool
    read: bool
    update: bool
    pause: bool
    resume: bool
    delete: bool
    production_qualified: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "server_url": self.server_url,
            "server_version": self.server_version,
            "schedule_api": self.schedule_api,
            "create": self.create,
            "read": self.read,
            "update": self.update,
            "pause": self.pause,
            "resume": self.resume,
            "delete": self.delete,
            "production_qualified": self.production_qualified,
        }


@dataclass(frozen=True, slots=True)
class ConnectScheduleDrift:
    """Read-only comparison of the canonical recurrence and Connect rule."""

    state: Literal["in_sync", "missing", "drifted", "unverifiable"]
    expected: Mapping[str, object] | None
    observed: Mapping[str, object] | None


@dataclass(frozen=True, slots=True)
class ConnectScheduleBinding:
    """Secret-free schedule ownership, including a durable operation claim.

    A pending binding marked ``registration`` records successful content
    deployment awaiting its first lifecycle operation. A claimed pending
    binding is single-writer state and cannot be taken over automatically
    while its writer may still be running. An unclassified pending binding
    fails closed.
    """

    schedule_id: str
    revision_id: str
    content_guid: str
    timer_owner_generation: int
    server_url: str
    target_url: str
    bundle_sha256: str
    # Immutable recurrence phase. The canonical next_fire_at cursor advances
    # after each occurrence and is not the remote schedule's start_time.
    schedule_start_time: str | None = None
    status: Literal["active", "paused", "deleted", "pending"] = "active"
    operation_id: str | None = None
    # Pending operation metadata is a durable single-writer claim. Registration
    # is explicit; an in-flight or unclassified operation is never taken over.
    pending_operation: (
        Literal["registration", "apply", "resume", "amend", "rollback"] | None
    ) = None
    pending_target_status: Literal["active", "paused", "deleted"] | None = None
    # False for bindings written before the runner accepted a generation override.
    supports_timer_generation_override: bool = False

    def __post_init__(self) -> None:
        for field_name in ("schedule_id", "revision_id", "content_guid"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be non-empty")
        if not _CONTENT_GUID.fullmatch(self.content_guid):
            raise ValueError("content_guid must be a Connect GUID")
        if (
            type(self.timer_owner_generation) is not int
            or self.timer_owner_generation < 1
        ):
            raise ValueError("timer_owner_generation must be a positive integer")
        if type(self.supports_timer_generation_override) is not bool:
            raise ValueError("supports_timer_generation_override must be a boolean")
        object.__setattr__(self, "server_url", _connect_base_url(self.server_url))
        parsed = urlsplit(self.target_url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("target_url must be an HTTPS URL without user information")
        try:
            if parsed.port is not None and not 1 <= parsed.port <= 65535:
                raise ValueError("target_url port is invalid")
        except ValueError as exc:
            raise ValueError("target_url port is invalid") from exc
        if self.status not in ("active", "paused", "deleted", "pending"):
            raise ValueError("binding status is unsupported")
        if not re.fullmatch(r"[0-9a-f]{64}", self.bundle_sha256):
            raise ValueError("bundle_sha256 must be a lowercase SHA-256 digest")
        if self.schedule_start_time is not None:
            try:
                start = datetime.fromisoformat(
                    self.schedule_start_time.replace("Z", "+00:00")
                )
            except (AttributeError, TypeError, ValueError) as exc:
                raise ValueError("schedule_start_time must be ISO-8601") from exc
            if start.tzinfo is None or start.utcoffset() is None:
                raise ValueError("schedule_start_time must include a timezone")
        if self.status == "pending":
            if not isinstance(self.operation_id, str) or not self.operation_id.strip():
                raise ValueError("pending binding requires an operation_id")
            if self.pending_operation not in (
                None,
                "registration",
                "apply",
                "resume",
                "amend",
                "rollback",
            ):
                raise ValueError("pending operation is unsupported")
            if self.pending_operation in (None, "registration"):
                if self.pending_target_status is not None:
                    raise ValueError(
                        "pending target status requires a claimed operation"
                    )
            elif self.pending_operation == "apply":
                if self.pending_target_status not in ("active", "paused", "deleted"):
                    raise ValueError("pending apply requires a target status")
            elif (
                self.pending_operation == "resume"
                and self.pending_target_status != "active"
            ):
                raise ValueError("pending resume must target active status")
            elif (
                self.pending_operation == "amend"
                and self.pending_target_status != "active"
            ):
                raise ValueError("pending amendment must target active status")
            elif (
                self.pending_operation == "rollback"
                and self.pending_target_status != "paused"
            ):
                raise ValueError("pending rollback must target paused status")
        elif self.operation_id is not None:
            raise ValueError("only pending bindings may retain an operation_id")
        elif (
            self.pending_operation is not None or self.pending_target_status is not None
        ):
            raise ValueError("only pending bindings may retain operation metadata")


class BindingStore(Protocol):
    """Host-owned durable store for Connect content ownership records.

    ``put`` and ``delete`` are atomic full-record compare-and-swap operations.
    A deployment registration is explicitly marked as such; the first
    lifecycle mutation changes it to a claimed pending operation before any
    remote write. Callers must never replace a claimed or unclassified pending
    operation while its writer may still be running. Exact remote readback does
    not prove that an in-flight writer has stopped. The implementation must
    serialize competing writes across processes.
    """

    def get(self, schedule_id: str) -> ConnectScheduleBinding | None: ...

    def put(
        self,
        binding: ConnectScheduleBinding,
        *,
        expected: ConnectScheduleBinding | None,
    ) -> None: ...

    def delete(self, schedule_id: str, *, expected: ConnectScheduleBinding) -> None: ...


class ConnectScheduleGateway(Protocol):
    """Mutation and readback surface required from a Connect SDK gateway."""

    @property
    def server_url(self) -> str: ...

    def read(self, content_guid: str) -> Any | None: ...

    def create_or_update(
        self, content_guid: str, kwargs: Mapping[str, object]
    ) -> Any: ...

    def delete(self, content_guid: str) -> None: ...

    def set_trigger_armed(self, content_guid: str, armed: bool) -> None: ...

    def set_trigger_generation(self, content_guid: str, generation: int) -> None: ...

    def can_set_trigger_armed(self, content_guid: str) -> bool: ...


class ConnectDeployer(Protocol):
    """Deployment identity needed to register a published bundle."""

    server_url: str


class PositSdkGateway:
    """Small adapter over the public Posit Python SDK object model.

    The SDK currently marks schedule mutations experimental. This gateway
    exposes that boundary instead of calling undocumented REST endpoints. It
    owns a separate SDK client pinned to the validated destination.
    """

    def __init__(
        self,
        client: Any,
        *,
        server_url: str,
        server_version: str | None = None,
    ) -> None:
        self._server_url = _connect_base_url(server_url)
        try:
            client_url = client.cfg.url
            if not isinstance(client_url, str):
                raise ValueError
            parsed_client_url = urlsplit(client_url)
            api_path = parsed_client_url.path.rstrip("/")
            if api_path == "/__api__":
                api_path = ""
            elif api_path.endswith("/__api__"):
                api_path = api_path[: -len("/__api__")]
            client_base_url = _connect_base_url(
                parsed_client_url._replace(path=api_path).geturl()
            )
        except (AttributeError, TypeError, ValueError):
            raise ValueError(
                "Posit SDK client must expose a valid HTTPS Connect destination"
            ) from None
        if client_base_url != self._server_url:
            raise ValueError(
                "Posit SDK client destination does not match the configured Connect server"
            )
        try:
            api_key = client.cfg.api_key
            if not isinstance(api_key, str) or not api_key:
                raise ValueError
            # The Posit SDK reads cfg.url for every request. Give this gateway
            # its own client so later changes to the caller's mutable config
            # cannot redirect requests or attach different credentials.
            pinned_client = type(client)(url=client_url, api_key=api_key)
            pinned_url = pinned_client.cfg.url
            if not isinstance(pinned_url, str):
                raise ValueError
            parsed_pinned_url = urlsplit(pinned_url)
            pinned_path = parsed_pinned_url.path.rstrip("/")
            if pinned_path == "/__api__":
                pinned_path = ""
            elif pinned_path.endswith("/__api__"):
                pinned_path = pinned_path[: -len("/__api__")]
            pinned_base_url = _connect_base_url(
                parsed_pinned_url._replace(path=pinned_path).geturl()
            )
        except Exception:
            raise ValueError(
                "Posit SDK client must support an isolated HTTPS Connect destination"
            ) from None
        if pinned_base_url != self._server_url:
            raise ValueError(
                "Posit SDK client destination does not match the configured Connect server"
            )
        source_session = getattr(client, "session", None)
        pinned_session = getattr(pinned_client, "session", None)
        if source_session is not None:
            if pinned_session is None:
                raise ValueError("Posit SDK client session could not be isolated")
            try:
                self._copy_session_configuration(source_session, pinned_session)
            except Exception:
                raise ValueError(
                    "Posit SDK client session configuration could not be isolated"
                ) from None
        self._client = pinned_client
        self._client_url = pinned_url
        self._server_version = server_version

    @staticmethod
    def _copy_session_configuration(source: Any, target: Any) -> None:
        """Copy public requests session settings without copying SDK auth."""
        for name in ("headers", "cookies", "proxies", "hooks", "params"):
            value = getattr(source, name)
            if name == "hooks":
                copied = {key: list(callbacks) for key, callbacks in value.items()}
            else:
                copier = getattr(value, "copy", None)
                copied = copier() if callable(copier) else copy(value)
            setattr(target, name, copied)
        for name in ("verify", "cert", "trust_env", "max_redirects"):
            setattr(target, name, getattr(source, name))

        source_adapters = source.adapters
        mount = target.mount
        for prefix, adapter in source_adapters.items():
            mount(prefix, PositSdkGateway._copy_transport_adapter(adapter))

    @staticmethod
    def _copy_transport_adapter(adapter: Any) -> Any:
        """Clone a transport adapter without losing subclass TLS settings."""
        clone_method = getattr(adapter, "clone", None)
        if callable(clone_method):
            cloned = clone_method()
            if cloned is adapter:
                raise ValueError("transport adapter cannot be isolated")
            return cloned

        requests_http_adapter = any(
            base.__module__ == "requests.adapters" and base.__name__ == "HTTPAdapter"
            for base in type(adapter).__mro__
        )
        if not requests_http_adapter:
            cloned = copy(adapter)
            if cloned is adapter:
                raise ValueError("transport adapter cannot be isolated")
            return cloned

        # HTTPAdapter's pickle state intentionally includes only its base
        # attributes. Its normal copy path therefore loses subclass values
        # such as an SSLContext before init_poolmanager runs. Restore the full
        # instance state first, then build a fresh connection pool through the
        # adapter's supported initialization hook.
        adapter_type = cast(type[Any], type(adapter))
        cloned: Any = object.__new__(adapter_type)
        excluded = {"poolmanager", "proxy_manager"}
        adapter_state = cast(Mapping[str, object], vars(adapter))
        state_names: set[str] = set(adapter_state)
        adapter_mro: tuple[type[Any], ...] = adapter_type.__mro__
        for cls in adapter_mro:
            slots: object = getattr(cls, "__slots__", ())
            slot_names: tuple[str, ...]
            if isinstance(slots, str):
                slot_names = (slots,)
            elif isinstance(slots, tuple):
                slot_values = cast(tuple[object, ...], slots)
                slot_names = tuple(
                    name for name in slot_values if isinstance(name, str)
                )
            else:
                slot_names = ()
            state_names.update(
                name for name in slot_names if name not in ("__dict__", "__weakref__")
            )
        for name in state_names - excluded:
            value: Any
            try:
                value = deepcopy(getattr(adapter, name))
            except Exception:
                try:
                    value = copy(getattr(adapter, name))
                except Exception:
                    value = getattr(adapter, name)
            setattr(cloned, name, value)
        cloned.proxy_manager = {}
        cloned.init_poolmanager(
            adapter._pool_connections,
            adapter._pool_maxsize,
            block=adapter._pool_block,
        )
        return cloned

    @property
    def server_url(self) -> str:
        return self._server_url

    @property
    def server_version(self) -> str | None:
        return self._server_version

    def _pinned_client(self) -> Any:
        try:
            current_url = self._client.cfg.url
        except AttributeError:
            current_url = None
        if current_url != self._client_url:
            raise ScheduleOperationError(
                "Posit SDK client destination changed; create a new gateway"
            )
        return self._client

    def _schedule(self, content_guid: str) -> Any:
        if not _CONTENT_GUID.fullmatch(content_guid):
            raise ScheduleOperationError("content_guid must be a Connect GUID")
        try:
            content = self._pinned_client().content.get(content_guid)
            schedule = content.schedule
        except Exception:
            raise ScheduleOperationError(
                "Posit SDK could not read the configured content schedule"
            ) from None
        if not all(
            callable(getattr(schedule, method, None))
            for method in ("create", "delete", "find_one")
        ):
            raise ScheduleOperationError(
                "installed Posit SDK does not expose schedule create/delete/read"
            )
        return schedule

    def read(self, content_guid: str) -> Any | None:
        try:
            return self._schedule(content_guid).find_one()
        except ScheduleOperationError:
            raise
        except Exception:
            raise ScheduleOperationError("Posit Connect schedule read failed") from None

    def create_or_update(self, content_guid: str, kwargs: Mapping[str, object]) -> Any:
        try:
            schedule = self._schedule(content_guid)
            return schedule.create(**dict(kwargs))
        except ScheduleOperationError:
            raise
        except Exception:
            raise ScheduleOperationUnknown(
                "Posit Connect schedule mutation outcome is unknown; reconcile before retry"
            ) from None

    def delete(self, content_guid: str) -> None:
        try:
            self._schedule(content_guid).delete()
        except ScheduleOperationError:
            raise
        except Exception:
            raise ScheduleOperationUnknown(
                "Posit Connect schedule deletion outcome is unknown; reconcile before retry"
            ) from None

    def set_trigger_armed(self, content_guid: str, armed: bool) -> None:
        """Set the generated script's disarmed-by-default environment switch."""
        try:
            content = self._pinned_client().content.get(content_guid)
            environment = content.environment_variables
            update = getattr(environment, "update", None)
            if not callable(update):
                raise ScheduleOperationError(
                    "installed Posit SDK does not expose content environment updates"
                )
            update({"ETLANTIC_TRIGGER_ARMED": "true" if armed else "false"})
        except ScheduleOperationError:
            raise
        except Exception:
            raise ScheduleOperationUnknown(
                "Posit Connect content arming outcome is unknown; inspect content before retrying"
            ) from None

    def set_trigger_generation(self, content_guid: str, generation: int) -> None:
        """Set the canonical timer generation read by an installed trigger."""
        if type(generation) is not int or generation < 1:
            raise ValueError("timer owner generation must be a positive integer")
        try:
            content = self._pinned_client().content.get(content_guid)
            environment = content.environment_variables
            update = getattr(environment, "update", None)
            if not callable(update):
                raise ScheduleOperationError(
                    "installed Posit SDK does not expose content environment updates"
                )
            update({"ETLANTIC_TIMER_OWNER_GENERATION": str(generation)})
        except ScheduleOperationError:
            raise
        except Exception:
            raise ScheduleOperationUnknown(
                "Posit Connect timer generation update outcome is unknown; inspect content before retrying"
            ) from None

    def can_set_trigger_armed(self, content_guid: str) -> bool:
        try:
            content = self._pinned_client().content.get(content_guid)
            return callable(
                getattr(getattr(content, "environment_variables", None), "update", None)
            )
        except Exception:
            return False

    def schedule_api_available(self, content_guid: str) -> bool:
        try:
            schedule = self._schedule(content_guid)
        except ScheduleOperationError:
            return False
        return all(
            callable(getattr(schedule, operation, None))
            for operation in ("create", "delete", "find_one")
        )


def _connect_base_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "Connect server URL must be HTTPS without user information, query, or fragment"
        )
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Connect server URL has an invalid port") from exc
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("Connect server URL has an invalid port")
    host = parsed.hostname.lower()
    port_text = f":{port}" if port is not None and port != 443 else ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    return f"https://{host}{port_text}{parsed.path.rstrip('/')}"


def _same_binding_target(
    left: ConnectScheduleBinding, right: ConnectScheduleBinding
) -> bool:
    return (
        left.schedule_id == right.schedule_id
        and left.revision_id == right.revision_id
        and left.content_guid == right.content_guid
        and left.timer_owner_generation == right.timer_owner_generation
        and left.server_url == right.server_url
        and left.target_url == right.target_url
        and left.bundle_sha256 == right.bundle_sha256
        and left.supports_timer_generation_override
        == right.supports_timer_generation_override
    )


def _schedule_rule_mapping(schedule: Any) -> Mapping[str, object] | None:
    raw_rule: object = getattr(schedule, "rule", None)
    if not isinstance(raw_rule, Mapping):
        return None
    raw_rule_mapping = cast(Mapping[object, object], raw_rule)
    # posit-sdk exposes the Connect payload as independent Schedule fields;
    # Schedule.rule only contains its decoded recurrence, e.g. {"N": 1}.
    schedule_type = getattr(schedule, "type", None)
    interval: object = raw_rule_mapping.get("N", raw_rule_mapping.get("n"))
    start_time = getattr(schedule, "start_time", None)
    if isinstance(start_time, datetime):
        start_time = start_time.astimezone(UTC).isoformat().replace("+00:00", "Z")
    elif isinstance(start_time, str):
        try:
            parsed = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        start_time = parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if (
        isinstance(schedule_type, str)
        and type(interval) is int
        and isinstance(start_time, str)
        and isinstance(getattr(schedule, "timezone", None), str)
        and type(getattr(schedule, "email", None)) is bool
    ):
        return {
            "type": schedule_type,
            "n": interval,
            "start_time": start_time,
            "timezone": schedule.timezone,
            "email": schedule.email,
        }
    # Keep compatibility with gateways that already return the canonical
    # request mapping, while refusing incomplete SDK objects.
    if set(raw_rule_mapping) == {"type", "n", "start_time", "timezone", "email"}:
        value = cast(Mapping[str, object], raw_rule_mapping)
        if (
            isinstance(value["type"], str)
            and type(value["n"]) is int
            and value["n"] > 0
            and isinstance(value["start_time"], str)
            and isinstance(value["timezone"], str)
            and type(value["email"]) is bool
        ):
            return value
    return None


def inspect_connect_capabilities(
    gateway: PositSdkGateway, content_guid: str
) -> ConnectCapabilityReport:
    """Report the configured content's SDK surface and experimental label."""
    available = gateway.schedule_api_available(content_guid)
    can_arm = gateway.can_set_trigger_armed(content_guid)
    return ConnectCapabilityReport(
        server_url=gateway.server_url,
        server_version=gateway.server_version,
        schedule_api="experimental" if available else "unavailable",
        create=available,
        read=available,
        update=available,
        pause=available and can_arm,
        resume=available and can_arm,
        delete=available,
    )


def _connect_recurrence(
    record: ScheduleRecord, *, start_time: str | None = None
) -> dict[str, object]:
    spec = record.spec
    if (
        spec.kind != "interval"
        or spec.interval_seconds is None
        or spec.interval_seconds % 60
        or spec.timezone != "UTC"
        or spec.misfire != "fire_once"
        or spec.jitter_seconds != 0
        or spec.window_start is not None
        or spec.window_end is not None
        or spec.overlap != "skip"
    ):
        raise ScheduleOperationError(
            "Connect pilot supports only UTC interval schedules with fire_once, no jitter, and no window"
        )
    seconds = spec.interval_seconds
    if seconds < 3600:
        schedule_type = "minute"
        interval = seconds // 60
    elif seconds < 86400 and seconds % 3600 == 0:
        schedule_type = "hour"
        interval = seconds // 3600
    elif seconds % 86400 == 0:
        schedule_type = "day"
        interval = seconds // 86400
    else:
        raise ScheduleOperationError(
            "interval is not exactly representable by the selected Connect schedule type"
        )
    recurrence_start = start_time or record.next_fire_at
    if recurrence_start is None:
        raise ScheduleOperationError("external schedule has no canonical next_fire_at")
    return {
        "type": schedule_type,
        "n": interval,
        "start_time": recurrence_start,
        "timezone": "UTC",
        "email": False,
    }


class ConnectScheduleAdapter:
    """Mirror a canonical externally owned schedule to one Connect content item.

    Mutations require explicit preview opt-in because the Posit SDK schedule
    interface is experimental. Callers supply a durable ownership store. The
    generated content remains disarmed until a schedule mutation succeeds.
    """

    def __init__(
        self,
        gateway: ConnectScheduleGateway,
        binding_store: BindingStore,
        *,
        allow_experimental_schedule_api: bool = False,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.gateway = gateway
        self.binding_store = binding_store
        self.allow_experimental_schedule_api = allow_experimental_schedule_api
        self.clock = clock

    def _require_preview(self) -> None:
        if not self.allow_experimental_schedule_api:
            raise ScheduleOperationError(
                "schedule mutation is experimental; set allow_experimental_schedule_api=True for a preview deployment"
            )

    def reconcile(
        self,
        record: ScheduleRecord,
        binding: ConnectScheduleBinding,
    ) -> Any | None:
        self._check_binding(record, binding)
        return self.gateway.read(binding.content_guid)

    def inspect_drift(
        self,
        record: ScheduleRecord,
        binding: ConnectScheduleBinding,
    ) -> ConnectScheduleDrift:
        """Compare the public SDK's decoded rule without modifying Connect."""
        self._check_binding(record, binding)
        schedule = self.gateway.read(binding.content_guid)
        if record.status in ("paused", "deleted"):
            if schedule is None:
                return ConnectScheduleDrift("in_sync", None, None)
            return ConnectScheduleDrift(
                "drifted", None, _schedule_rule_mapping(schedule)
            )
        expected = _connect_recurrence(record, start_time=binding.schedule_start_time)
        if schedule is None:
            return ConnectScheduleDrift("missing", expected, None)
        observed = _schedule_rule_mapping(schedule)
        if observed is None:
            return ConnectScheduleDrift("unverifiable", expected, None)
        return ConnectScheduleDrift(
            "in_sync" if dict(observed) == expected else "drifted",
            expected,
            observed,
        )

    def register_deployed_content(
        self,
        record: ScheduleRecord,
        bundle: TriggerBundle,
        deployment: DeploymentResult,
        deployer: ConnectDeployer,
    ) -> ConnectScheduleBinding:
        """Persist ownership for a newly published, still-unscheduled item."""
        self._require_preview()
        self._check_binding(
            record,
            ConnectScheduleBinding(
                schedule_id=record.schedule_id,
                revision_id=record.revision_id,
                content_guid=deployment.content_guid,
                timer_owner_generation=record.timer_owner_generation,
                server_url=deployer.server_url,
                target_url=bundle.endpoint_url,
                bundle_sha256=bundle.sha256,
                supports_timer_generation_override=(
                    bundle.supports_timer_generation_override
                ),
                status="active",
            ),
        )
        if record.timer_owner != "external" or record.status != "active":
            raise ScheduleOperationError(
                "content can be registered only for an active externally owned schedule"
            )
        if record.next_fire_at is None:
            raise ScheduleOperationError(
                "content cannot be registered without a canonical next_fire_at cursor"
            )
        if (
            deployer.server_url != self.gateway.server_url
            or deployment.server_url != self.gateway.server_url
        ):
            raise ScheduleOperationError(
                "deployment result targets a different Connect server"
            )
        if (
            deployment.state != "deployed"
            or deployment.bundle_sha256 != bundle.sha256
            or bundle.schedule_id != record.schedule_id
            or bundle.schedule_revision_id != record.revision_id
            or bundle.timer_owner_generation != record.timer_owner_generation
            or not deployment.operation_id.strip()
        ):
            raise ScheduleOperationError(
                "deployment result or trigger bundle does not match the canonical schedule"
            )
        if self.binding_store.get(record.schedule_id) is not None:
            raise ScheduleOperationError(
                "a durable Connect binding already exists; reconcile before deployment"
            )
        if self.gateway.read(deployment.content_guid) is not None:
            raise ScheduleOperationError(
                "newly deployed content already has a Connect schedule; reconcile before binding"
            )
        binding = ConnectScheduleBinding(
            schedule_id=record.schedule_id,
            revision_id=record.revision_id,
            content_guid=deployment.content_guid,
            timer_owner_generation=record.timer_owner_generation,
            server_url=self.gateway.server_url,
            target_url=bundle.endpoint_url,
            bundle_sha256=bundle.sha256,
            supports_timer_generation_override=(
                bundle.supports_timer_generation_override
            ),
            schedule_start_time=record.next_fire_at,
            status="pending",
            operation_id=deployment.operation_id,
            pending_operation="registration",
        )
        self.binding_store.put(binding, expected=None)
        return binding

    def apply(
        self,
        record: ScheduleRecord,
        binding: ConnectScheduleBinding,
    ) -> ConnectScheduleBinding:
        self._require_preview()
        self._check_binding(record, binding)
        if record.timer_owner != "external":
            raise ScheduleOperationError("canonical schedule is not externally owned")
        if binding.server_url != self.gateway.server_url:
            raise ScheduleOperationError("binding targets a different Connect server")
        observed = self.binding_store.get(record.schedule_id)
        if observed is None:
            raise ScheduleOperationError(
                "Connect content must be registered from a successful deployment before scheduling"
            )
        if observed.status == "pending":
            if not _same_binding_target(observed, binding):
                raise ScheduleOperationUnknown(
                    "a prior Connect mutation is pending for a different content binding; inspect remote state before retrying"
                )
            if observed.pending_operation is None:
                raise ScheduleOperationUnknown(
                    "pending binding has no recognized operation type; inspect remote state before retrying"
                )
            if observed.pending_operation == "amend":
                raise ScheduleOperationUnknown(
                    "a Connect amendment is pending; inspect remote and canonical state before retrying"
                )
            if observed.pending_operation == "resume" and record.status != "active":
                raise ScheduleOperationUnknown(
                    "a Connect resume is pending for a different canonical state; reconcile before retrying"
                )
            if observed.pending_operation in ("apply", "resume", "rollback"):
                raise ScheduleOperationUnknown(
                    "a Connect lifecycle mutation is still pending; confirm its writer has stopped before reconciliation"
                )
        else:
            if (
                observed.schedule_id != binding.schedule_id
                or observed.content_guid != binding.content_guid
                or observed.revision_id != binding.revision_id
                or observed.timer_owner_generation != binding.timer_owner_generation
                or observed.server_url != binding.server_url
                or observed.target_url != binding.target_url
                or observed.bundle_sha256 != binding.bundle_sha256
                or observed.supports_timer_generation_override
                != binding.supports_timer_generation_override
                or observed.schedule_start_time != binding.schedule_start_time
                or observed.status != binding.status
            ):
                raise ScheduleOperationError(
                    "Connect ownership binding changed; reconcile manually before mutation"
                )
        if observed.status == "deleted" and record.status != "deleted":
            raise ScheduleOperationError(
                "deleted Connect content binding cannot be reactivated"
            )
        if record.status == "active":
            # Resuming a paused binding starts a new phase at the current
            # canonical cursor. Active cursors advance independently thereafter.
            schedule_start = (
                record.next_fire_at
                if observed.status == "paused"
                else (
                    observed.schedule_start_time
                    if observed.status == "pending"
                    else binding.schedule_start_time
                )
            )
            desired = _connect_recurrence(record, start_time=schedule_start)
            remote = self.gateway.read(binding.content_guid)
            if observed.status == "active":
                observed_rule = _schedule_rule_mapping(remote) if remote else None
                if observed_rule is None or dict(observed_rule) != desired:
                    raise ScheduleOperationError(
                        "Connect schedule drift detected; reconcile before mutation"
                    )
            elif observed.status == "pending" and remote is not None:
                observed_rule = _schedule_rule_mapping(remote)
                if observed_rule is None or dict(observed_rule) != desired:
                    raise ScheduleOperationUnknown(
                        "pending Connect mutation has unexplained remote state; reconcile before retrying"
                    )
            elif observed.status == "paused" and remote is not None:
                raise ScheduleOperationError(
                    "Connect schedule drift detected for a paused binding; reconcile before mutation"
                )
            intent = replace(
                observed,
                schedule_start_time=schedule_start,
                status="pending",
                operation_id=uuid.uuid4().hex,
                pending_operation="apply",
                pending_target_status="active",
            )
            try:
                self.binding_store.put(intent, expected=observed)
            except Exception:
                raise ScheduleOperationUnknown(
                    "another Connect operation claimed this binding; reconcile before retrying"
                ) from None
            # Existing renders become inert before a recurrence mutation. A
            # failed write leaves the operation pending for operator recovery.
            self.gateway.set_trigger_armed(binding.content_guid, False)
            self._set_trigger_generation(
                binding.content_guid, record.timer_owner_generation
            )
            if observed.status != "pending" or remote is None:
                self.gateway.create_or_update(binding.content_guid, desired)
            self._verify_schedule_rule(binding.content_guid, desired)
            self.gateway.set_trigger_armed(binding.content_guid, True)
            active = replace(
                intent,
                status="active",
                operation_id=None,
                pending_operation=None,
                pending_target_status=None,
            )
            try:
                self.binding_store.put(active, expected=intent)
            except Exception:
                raise ScheduleOperationUnknown(
                    "Connect was updated but the ownership result could not be committed; reconcile before retrying"
                ) from None
            return active
        if record.status in ("paused", "deleted"):
            if observed.status == "deleted":
                return observed
            remote = self.gateway.read(binding.content_guid)
            if observed.status == "active" and remote is not None:
                expected = _connect_recurrence(
                    record, start_time=binding.schedule_start_time
                )
                observed_rule = _schedule_rule_mapping(remote)
                if observed_rule is None or dict(observed_rule) != expected:
                    raise ScheduleOperationError(
                        "Connect schedule drift detected; reconcile before mutation"
                    )
            elif remote is not None:
                raise ScheduleOperationError(
                    "Connect schedule drift detected for a non-active binding; reconcile before mutation"
                )
            intent = replace(
                observed,
                status="pending",
                operation_id=uuid.uuid4().hex,
                pending_operation="apply",
                pending_target_status=record.status,
            )
            try:
                self.binding_store.put(intent, expected=observed)
            except Exception:
                raise ScheduleOperationUnknown(
                    "another Connect operation claimed this binding; reconcile before retrying"
                ) from None
            self.gateway.set_trigger_armed(binding.content_guid, False)
            self.gateway.delete(binding.content_guid)
            self._verify_schedule_absent(binding.content_guid)
            updated = replace(
                intent,
                status=record.status,
                operation_id=None,
                pending_operation=None,
                pending_target_status=None,
            )
            if record.status == "deleted":
                self.binding_store.put(updated, expected=intent)
                return updated
            self.binding_store.put(updated, expected=intent)
            return updated
        raise ScheduleOperationError("canonical schedule state is unsupported")

    def _verify_schedule_rule(
        self, content_guid: str, expected: Mapping[str, object]
    ) -> None:
        try:
            schedule = self.gateway.read(content_guid)
        except Exception:
            raise ScheduleOperationUnknown(
                "Connect schedule write may have committed but readback failed; reconcile before retrying"
            ) from None
        observed = _schedule_rule_mapping(schedule) if schedule is not None else None
        if observed is None or dict(observed) != dict(expected):
            raise ScheduleOperationUnknown(
                "Connect schedule write may have committed but readback did not match; reconcile before retrying"
            )

    def _verify_schedule_absent(self, content_guid: str) -> None:
        try:
            schedule = self.gateway.read(content_guid)
        except Exception:
            raise ScheduleOperationUnknown(
                "Connect schedule deletion may have committed but readback failed; reconcile before retrying"
            ) from None
        if schedule is not None:
            raise ScheduleOperationUnknown(
                "Connect schedule deletion may have committed but the schedule remains; reconcile before retrying"
            )

    def _set_trigger_generation(self, content_guid: str, generation: int) -> None:
        update = getattr(self.gateway, "set_trigger_generation", None)
        if not callable(update):
            raise ScheduleOperationError(
                "Connect gateway cannot update the installed trigger generation"
            )
        update(content_guid, generation)

    def pause(
        self,
        service: ScheduleApplicationService,
        context: ControlPlaneContext,
        schedule_id: str,
        binding: ConnectScheduleBinding,
    ) -> ConnectScheduleBinding:
        self._require_preview()
        current = service.get(context, schedule_id)
        self._preflight_control_plane_binding(current, binding)
        service.authorize(context, "schedule.write", f"schedule:{schedule_id}")
        intent = self._claim_lifecycle_apply(binding, "paused")
        record = service.pause(context, schedule_id)
        return self._finish_lifecycle_apply(record, intent, binding)

    def delete(
        self,
        service: ScheduleApplicationService,
        context: ControlPlaneContext,
        schedule_id: str,
        binding: ConnectScheduleBinding,
    ) -> ConnectScheduleBinding:
        """Deny canonical admissions first, then remove the owned timer."""
        self._require_preview()
        current = service.get(context, schedule_id)
        self._preflight_control_plane_binding(current, binding)
        service.authorize(context, "schedule.write", f"schedule:{schedule_id}")
        intent = self._claim_lifecycle_apply(binding, "deleted")
        record = service.delete(context, schedule_id)
        return self._finish_lifecycle_apply(record, intent, binding)

    def _verify_lifecycle_remote_state(
        self, record: ScheduleRecord, binding: ConnectScheduleBinding
    ) -> None:
        try:
            remote = self.gateway.read(binding.content_guid)
        except Exception:
            raise ScheduleOperationUnknown(
                "canonical schedule was stopped but Connect state could not be read; reconcile before retrying"
            ) from None
        if binding.status == "active":
            expected = _connect_recurrence(
                record, start_time=binding.schedule_start_time
            )
            observed = _schedule_rule_mapping(remote) if remote is not None else None
            if observed is None or dict(observed) != expected:
                raise ScheduleOperationError(
                    "Connect schedule drift detected; reconcile before mutation"
                )
        elif remote is not None:
            raise ScheduleOperationError(
                "Connect schedule drift detected for a non-active binding; reconcile before mutation"
            )

    def _claim_lifecycle_apply(
        self,
        binding: ConnectScheduleBinding,
        target_status: Literal["paused", "deleted"],
    ) -> ConnectScheduleBinding:
        intent = replace(
            binding,
            status="pending",
            operation_id=uuid.uuid4().hex,
            pending_operation="apply",
            pending_target_status=target_status,
        )
        try:
            self.binding_store.put(intent, expected=binding)
        except Exception:
            raise ScheduleOperationUnknown(
                "another Connect operation claimed this binding; reconcile before retrying"
            ) from None
        return intent

    def _finish_lifecycle_apply(
        self,
        record: ScheduleRecord,
        intent: ConnectScheduleBinding,
        prior_binding: ConnectScheduleBinding,
    ) -> ConnectScheduleBinding:
        target_status = intent.pending_target_status
        if (
            intent.status != "pending"
            or intent.pending_operation != "apply"
            or target_status not in ("paused", "deleted")
        ):
            raise ScheduleOperationError("Connect lifecycle claim is invalid")
        self._check_binding(record, intent)
        if record.timer_owner != "external" or record.status != target_status:
            raise ScheduleOperationUnknown(
                "canonical lifecycle mutation did not reach the claimed state"
            )
        # The canonical operation may take time. Recheck Connect after claiming
        # ownership so a schedule changed during that interval is not removed.
        self._verify_lifecycle_remote_state(record, prior_binding)
        self.gateway.set_trigger_armed(intent.content_guid, False)
        self.gateway.delete(intent.content_guid)
        self._verify_schedule_absent(intent.content_guid)
        updated = replace(
            intent,
            status=target_status,
            operation_id=None,
            pending_operation=None,
            pending_target_status=None,
        )
        try:
            self.binding_store.put(updated, expected=intent)
        except Exception:
            raise ScheduleOperationUnknown(
                "canonical lifecycle mutation completed but Connect ownership could not be committed; reconcile before retrying"
            ) from None
        return updated

    def _claim_amendment_rollback(
        self, pending: ConnectScheduleBinding
    ) -> ConnectScheduleBinding | None:
        rollback = replace(
            pending,
            operation_id=uuid.uuid4().hex,
            pending_operation="rollback",
            pending_target_status="paused",
        )
        try:
            self.binding_store.put(rollback, expected=pending)
        except Exception:
            return None
        return rollback

    def _rollback_amendment(
        self,
        service: ScheduleApplicationService,
        context: ControlPlaneContext,
        schedule_id: str,
        pending: ConnectScheduleBinding,
    ) -> None:
        rollback = self._claim_amendment_rollback(pending)
        if rollback is None:
            return
        with suppress(Exception):
            self.gateway.set_trigger_armed(rollback.content_guid, False)
        with suppress(Exception):
            service.pause(context, schedule_id)

    def resume(
        self,
        service: ScheduleApplicationService,
        context: ControlPlaneContext,
        schedule_id: str,
        binding: ConnectScheduleBinding,
        *,
        build_bundle: Callable[[ScheduleRecord], TriggerBundle] | None = None,
        deployer: RsconnectPythonDeployer | None = None,
        title: str | None = None,
    ) -> ConnectScheduleBinding:
        self._require_preview()
        current = service.get(context, schedule_id)
        self._preflight_control_plane_binding(current, binding)
        if current.status != "paused" or binding.status != "paused":
            raise ScheduleOperationError(
                "resume requires a paused canonical schedule and paused Connect binding"
            )
        if current.next_fire_at is None:
            raise ScheduleOperationError(
                "resume requires a canonical next_fire_at cursor"
            )
        try:
            next_fire = datetime.fromisoformat(
                current.next_fire_at.replace("Z", "+00:00")
            )
            now = self.clock()
            if now.tzinfo is None or now.utcoffset() is None:
                raise ValueError("clock must return an aware datetime")
        except (AttributeError, TypeError, ValueError):
            raise ScheduleOperationError(
                "resume cannot verify the canonical next_fire_at cursor"
            ) from None
        if next_fire.astimezone(UTC) <= now.astimezone(UTC):
            raise ScheduleOperationError(
                "canonical next_fire_at has passed; amend or reconcile the cursor before resuming"
            )
        upgrade_bundle: TriggerBundle | None = None
        upgrade_deployer: RsconnectPythonDeployer | None = None
        if not binding.supports_timer_generation_override:
            if build_bundle is None or deployer is None or title is None:
                raise ScheduleOperationError(
                    "this deployed trigger cannot accept a resumed timer generation; "
                    "upgrade it during resume with build_bundle, deployer, and title"
                )
            if (
                deployer.server_url != binding.server_url
                or binding.server_url != self.gateway.server_url
            ):
                raise ScheduleOperationError(
                    "trigger upgrade deployer targets a different Connect server"
                )
            try:
                upgrade_bundle = build_bundle(current)
            except Exception as exc:
                raise ScheduleOperationError(
                    "generation-aware trigger bundle could not be built"
                ) from exc
            if (
                upgrade_bundle.schedule_id != current.schedule_id
                or upgrade_bundle.schedule_revision_id != current.revision_id
                or upgrade_bundle.timer_owner_generation
                != current.timer_owner_generation
                or upgrade_bundle.endpoint_url != binding.target_url
                or upgrade_bundle.supports_timer_generation_override is not True
            ):
                raise ScheduleOperationError(
                    "generation-aware trigger bundle does not match the paused binding"
                )
            upgrade_deployer = deployer
        elif build_bundle is not None or deployer is not None or title is not None:
            raise ScheduleOperationError(
                "bundle upgrade arguments are only valid for legacy trigger bindings"
            )
        if self.gateway.read(binding.content_guid) is not None:
            raise ScheduleOperationError(
                "Connect schedule drift detected for a paused binding; reconcile before resuming"
            )
        intent = replace(
            binding,
            schedule_start_time=current.next_fire_at,
            status="pending",
            operation_id=uuid.uuid4().hex,
            pending_operation="resume",
            pending_target_status="active",
        )
        try:
            self.binding_store.put(intent, expected=binding)
        except Exception:
            raise ScheduleOperationUnknown(
                "another Connect operation claimed this binding; reconcile before resuming"
            ) from None
        try:
            if upgrade_bundle is not None and upgrade_deployer is not None:
                self.gateway.set_trigger_armed(binding.content_guid, False)
                deployment = upgrade_deployer.deploy(
                    upgrade_bundle,
                    schedule_id=current.schedule_id,
                    operation_id=intent.operation_id or uuid.uuid4().hex,
                    title=cast(str, title),
                    existing_content_guid=binding.content_guid,
                )
                if (
                    deployment.content_guid != binding.content_guid
                    or deployment.state != "updated"
                    or deployment.bundle_sha256 != upgrade_bundle.sha256
                    or deployment.server_url != binding.server_url
                    or not deployment.operation_id.strip()
                ):
                    raise ScheduleOperationUnknown(
                        "generation-aware trigger deployment did not update the owned Connect content"
                    )
                upgraded_intent = replace(
                    intent,
                    bundle_sha256=upgrade_bundle.sha256,
                    supports_timer_generation_override=True,
                )
                try:
                    self.binding_store.put(upgraded_intent, expected=intent)
                except Exception:
                    raise ScheduleOperationUnknown(
                        "trigger was upgraded but its generation support could not be committed; reconcile before resuming"
                    ) from None
                intent = upgraded_intent
            record = service.resume(context, schedule_id)
            if record.status != "active":
                raise ScheduleOperationUnknown(
                    "canonical schedule did not become active during Connect resume"
                )
            if (
                record.schedule_id != intent.schedule_id
                or record.revision_id != intent.revision_id
            ):
                raise ScheduleOperationUnknown(
                    "canonical schedule changed during Connect resume"
                )
            resumed_intent = replace(
                intent,
                timer_owner_generation=record.timer_owner_generation,
                schedule_start_time=(
                    record.timer_schedule_start_at or intent.schedule_start_time
                ),
            )
            if resumed_intent != intent:
                try:
                    self.binding_store.put(resumed_intent, expected=intent)
                except Exception:
                    raise ScheduleOperationUnknown(
                        "canonical schedule resumed but its timer generation could not be committed; reconcile before retrying"
                    ) from None
                intent = resumed_intent
            self._check_binding(record, intent)
            if self.gateway.read(binding.content_guid) is not None:
                raise ScheduleOperationUnknown(
                    "Connect schedule appeared during resume; reconcile before mutation"
                )
            desired = _connect_recurrence(record, start_time=intent.schedule_start_time)
            self.gateway.set_trigger_armed(binding.content_guid, False)
            self._set_trigger_generation(
                binding.content_guid, record.timer_owner_generation
            )
            self.gateway.create_or_update(binding.content_guid, desired)
            self._verify_schedule_rule(binding.content_guid, desired)
            self.gateway.set_trigger_armed(binding.content_guid, True)
            active = replace(
                intent,
                status="active",
                operation_id=None,
                pending_operation=None,
                pending_target_status=None,
            )
            try:
                self.binding_store.put(active, expected=intent)
            except Exception:
                raise ScheduleOperationUnknown(
                    "Connect resumed but its ownership result could not be committed; reconcile before retrying"
                ) from None
            return active
        except Exception:
            rollback_claim = replace(
                intent,
                operation_id=uuid.uuid4().hex,
                pending_operation="rollback",
                pending_target_status="paused",
            )
            try:
                # Fence cleanup atomically before disarming or changing the
                # canonical schedule. A read cannot protect these side effects
                # from a concurrent recovery that commits after the read.
                self.binding_store.put(rollback_claim, expected=intent)
            except Exception:
                rollback_claimed = False
            else:
                rollback_claimed = True
            if rollback_claimed:
                with suppress(Exception):
                    self.gateway.set_trigger_armed(binding.content_guid, False)
                with suppress(Exception):
                    service.pause(context, schedule_id)
            raise

    def amend(
        self,
        service: ScheduleApplicationService,
        context: ControlPlaneContext,
        schedule_id: str,
        binding: ConnectScheduleBinding,
        *,
        expected_revision_id: str,
        spec: ScheduleSpec,
        build_bundle: Callable[[ScheduleRecord], TriggerBundle],
        deployer: RsconnectPythonDeployer,
        title: str,
        operation_id: str,
    ) -> ConnectScheduleBinding:
        """Update a schedule while admissions and content delivery are paused."""
        self._require_preview()
        current = service.get(context, schedule_id)
        self._check_binding(current, binding)
        if current.timer_owner != "external":
            raise ScheduleOperationError("canonical schedule is not externally owned")
        if binding.server_url != self.gateway.server_url:
            raise ScheduleOperationError("binding targets a different Connect server")
        if current.status != "active":
            raise ScheduleOperationError(
                "schedule amendment requires an active schedule"
            )
        if expected_revision_id != current.revision_id:
            raise ScheduleOperationError(
                "expected revision is stale; reload the schedule before amendment"
            )
        # Reject unsupported recurrence changes before pausing canonical
        # admissions, claiming the binding, or publishing replacement content.
        _connect_recurrence(
            replace(current, spec=spec), start_time=current.next_fire_at
        )
        operation_id_value: object = cast(object, operation_id)
        if (
            not isinstance(operation_id_value, str)
            or not operation_id_value.strip()
            or len(operation_id_value) > 256
        ):
            raise ValueError("operation_id must be non-empty")
        if deployer.server_url != self.gateway.server_url:
            raise ScheduleOperationError(
                "deployer and schedule gateway target different Connect servers"
            )
        observed = self.binding_store.get(schedule_id)
        if observed != binding:
            raise ScheduleOperationError(
                "Connect ownership binding changed; reconcile before amendment"
            )
        if binding.status != "active":
            raise ScheduleOperationError(
                "schedule amendment requires an active Connect binding"
            )
        expected_remote_rule = _connect_recurrence(
            current, start_time=binding.schedule_start_time
        )
        remote = self.gateway.read(binding.content_guid)
        observed_remote_rule = (
            _schedule_rule_mapping(remote) if remote is not None else None
        )
        if (
            observed_remote_rule is None
            or dict(observed_remote_rule) != expected_remote_rule
        ):
            raise ScheduleOperationError(
                "Connect schedule drift detected; reconcile before amendment"
            )
        intent = replace(
            binding,
            status="pending",
            operation_id=operation_id,
            pending_operation="amend",
            pending_target_status="active",
        )
        try:
            self.binding_store.put(intent, expected=observed)
        except Exception:
            raise ScheduleOperationUnknown(
                "another Connect operation claimed this binding; reconcile before retrying"
            ) from None
        service.pause(context, schedule_id)
        self.gateway.set_trigger_armed(binding.content_guid, False)
        amended = service.amend(
            context,
            schedule_id,
            expected_revision_id=expected_revision_id,
            spec=spec,
        )
        if amended.status != "paused":
            raise ScheduleOperationUnknown(
                "canonical schedule amendment did not remain paused"
            )
        resumed = service.resume(context, schedule_id)
        if (
            resumed.status != "active"
            or resumed.schedule_id != amended.schedule_id
            or resumed.revision_id != amended.revision_id
        ):
            raise ScheduleOperationUnknown(
                "canonical schedule did not resume at the amended revision"
            )
        pending = replace(
            intent,
            revision_id=resumed.revision_id,
            timer_owner_generation=resumed.timer_owner_generation,
            schedule_start_time=(
                resumed.timer_schedule_start_at or resumed.next_fire_at
            ),
        )
        try:
            self.binding_store.put(pending, expected=intent)
        except Exception:
            raise ScheduleOperationUnknown(
                "canonical amendment resumed but its timer generation could not be committed; reconcile before retrying"
            ) from None
        try:
            desired = _connect_recurrence(
                resumed, start_time=pending.schedule_start_time
            )
            new_bundle = build_bundle(resumed)
            if (
                new_bundle.schedule_id != resumed.schedule_id
                or new_bundle.schedule_revision_id != resumed.revision_id
                or new_bundle.timer_owner_generation != resumed.timer_owner_generation
            ):
                raise ScheduleOperationError(
                    "rebuilt trigger bundle does not match the amended schedule"
                )
            deployment = deployer.deploy(
                new_bundle,
                schedule_id=resumed.schedule_id,
                operation_id=intent.operation_id or uuid.uuid4().hex,
                title=title,
                existing_content_guid=binding.content_guid,
            )
            if deployment.content_guid != binding.content_guid:
                raise ScheduleOperationUnknown(
                    "Connect update returned a different content ID; reconcile ownership before proceeding"
                )
            deployed_pending = replace(
                pending,
                target_url=new_bundle.endpoint_url,
                bundle_sha256=new_bundle.sha256,
                supports_timer_generation_override=(
                    new_bundle.supports_timer_generation_override
                ),
            )
        except Exception:
            self._rollback_amendment(service, context, schedule_id, pending)
            raise
        try:
            self.binding_store.put(deployed_pending, expected=pending)
        except Exception:
            self._rollback_amendment(service, context, schedule_id, pending)
            raise ScheduleOperationUnknown(
                "canonical amendment was saved but its new binding could not be committed; reconcile before retrying"
            ) from None
        pending = deployed_pending
        # Replacing a differently typed rule by merge can retain stale fields;
        # remove the old timer before creating the exact desired rule.
        try:
            self.gateway.delete(binding.content_guid)
            self._verify_schedule_absent(binding.content_guid)
            self.gateway.create_or_update(binding.content_guid, desired)
            self._verify_schedule_rule(binding.content_guid, desired)
        except Exception:
            self._rollback_amendment(service, context, schedule_id, pending)
            raise
        try:
            self._set_trigger_generation(
                binding.content_guid, resumed.timer_owner_generation
            )
            self.gateway.set_trigger_armed(binding.content_guid, True)
        except Exception:
            self._rollback_amendment(service, context, schedule_id, pending)
            raise
        active = replace(
            pending,
            revision_id=resumed.revision_id,
            status="active",
            operation_id=None,
            pending_operation=None,
            pending_target_status=None,
        )
        try:
            self.binding_store.put(active, expected=pending)
        except Exception:
            self._rollback_amendment(service, context, schedule_id, pending)
            raise ScheduleOperationUnknown(
                "Connect amendment succeeded but ownership could not be committed; reconcile before retrying"
            ) from None
        return active

    @staticmethod
    def _check_binding(record: ScheduleRecord, binding: ConnectScheduleBinding) -> None:
        if record.schedule_id != binding.schedule_id:
            raise ScheduleOperationError("binding schedule_id does not match record")
        if record.revision_id != binding.revision_id:
            raise ScheduleOperationError("binding revision is stale")
        if record.timer_owner_generation != binding.timer_owner_generation:
            raise ScheduleOperationError("binding timer owner generation is stale")

    def _preflight_control_plane_binding(
        self, record: ScheduleRecord, binding: ConnectScheduleBinding
    ) -> None:
        self._check_binding(record, binding)
        if record.timer_owner != "external":
            raise ScheduleOperationError("canonical schedule is not externally owned")
        if binding.server_url != self.gateway.server_url:
            raise ScheduleOperationError("binding targets a different Connect server")
        observed = self.binding_store.get(record.schedule_id)
        if observed is None:
            raise ScheduleOperationError(
                "Connect ownership binding is not durably registered"
            )
        if observed.status == "pending":
            raise ScheduleOperationUnknown(
                "a prior Connect mutation is pending; inspect remote state before retrying"
            )
        if observed != binding:
            raise ScheduleOperationError(
                "Connect ownership binding changed; reconcile before mutation"
            )
        if record.status != binding.status:
            raise ScheduleOperationError(
                "canonical schedule and Connect binding lifecycle states differ"
            )
