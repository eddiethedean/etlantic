"""RunIntent, RunSelection, RunRequest, and execution policies."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, cast

from etlantic.extensions import validate_extension_metadata
from etlantic.model import LogicalGraph
from etlantic.plan.freeze import deep_freeze, mutable_copy
from etlantic.plan.slicing import (
    dependency_closure,
    run_one_selection,
    run_until_selection,
    validate_selection_target,
)


def _string_values(
    value: object,
    *,
    name: str,
    allow_sets: bool = False,
) -> tuple[str, ...]:
    containers: tuple[type[Any], ...] = (list, tuple, set, frozenset)
    if not allow_sets:
        containers = (list, tuple)
    if not isinstance(value, containers):
        raise TypeError(f"{name} must be a list of strings")
    values = cast(Iterable[object], value)
    materialized = tuple(values)
    if not all(isinstance(item, str) for item in materialized):
        raise TypeError(f"{name} must be a list of strings")
    return tuple(cast(str, item) for item in materialized)


class RunIntent(StrEnum):
    """Why a pipeline run was requested."""

    STANDARD = "standard"
    INITIALIZE = "initialize"
    INCREMENTAL = "incremental"
    REFRESH = "refresh"
    VALIDATE = "validate"
    REPAIR = "repair"
    BACKFILL = "backfill"
    REPLAY = "replay"
    RESUME = "resume"


class MaterializationPolicy(StrEnum):
    """How intermediate artifacts should be materialized for a run."""

    DEFAULT = "default"
    NONE = "none"
    EAGER = "eager"
    DURABLE = "durable"


class InvalidationMode(StrEnum):
    """How prior artifacts are invalidated for a rerun."""

    NONE = "none"
    TARGET = "target"
    DOWNSTREAM = "downstream"
    CLOSURE = "closure"


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Retry behavior for steps and runs."""

    max_attempts: int = 1
    backoff_seconds: float = 0.0
    retry_on: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_attempts": self.max_attempts,
            "backoff_seconds": self.backoff_seconds,
            "retry_on": list(self.retry_on),
        }


@dataclass(frozen=True, slots=True)
class TimeoutPolicy:
    """Timeout behavior for runs and steps."""

    run_seconds: float | None = None
    step_seconds: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_seconds": self.run_seconds,
            "step_seconds": self.step_seconds,
        }


@dataclass(frozen=True, slots=True)
class CancellationPolicy:
    """Cancellation behavior."""

    cooperative: bool = True
    abandon_after_seconds: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "cooperative": self.cooperative,
            "abandon_after_seconds": self.abandon_after_seconds,
        }


@dataclass(frozen=True, slots=True)
class RunSelection:
    """Graph selection describing which nodes participate in a run."""

    kind: str
    nodes: tuple[str, ...] = ()
    tags: frozenset[str] = frozenset()
    start: str | None = None
    end: str | None = None

    @classmethod
    def all(cls) -> RunSelection:
        return cls(kind="all")

    @classmethod
    def only(cls, *nodes: str) -> RunSelection:
        return cls(kind="only", nodes=tuple(nodes))

    @classmethod
    def until(cls, step: str) -> RunSelection:
        return cls(kind="until", end=step)

    @classmethod
    def from_(cls, step: str) -> RunSelection:
        return cls(kind="from", start=step)

    @classmethod
    def between(cls, start: str, end: str) -> RunSelection:
        return cls(kind="between", start=start, end=end)

    @classmethod
    def upstream_of(cls, step: str) -> RunSelection:
        return cls(kind="upstream_of", end=step)

    @classmethod
    def downstream_of(cls, step: str) -> RunSelection:
        return cls(kind="downstream_of", start=step)

    @classmethod
    def matching(cls, *, tags: set[str] | frozenset[str]) -> RunSelection:
        return cls(kind="matching", tags=frozenset(tags))

    def resolve(self, graph: LogicalGraph) -> tuple[str, ...]:
        """Resolve this selection to declaration-ordered node names."""
        names = [n.name for n in graph.nodes]
        name_set = set(names)
        if self.kind == "all":
            return tuple(names)
        if self.kind == "only":
            missing = set(self.nodes) - name_set
            if missing:
                raise ValueError(f"Unknown step(s): {', '.join(sorted(missing))}")
            return dependency_closure(graph, set(self.nodes))
        if self.kind == "until":
            assert self.end is not None
            return run_until_selection(graph, self.end)
        if self.kind == "from":
            assert self.start is not None
            validate_selection_target(graph, self.start)
            started = False
            selected: list[str] = []
            for name in names:
                if name == self.start:
                    started = True
                if started:
                    selected.append(name)
            # Include upstream closure of the start so inputs exist.
            return dependency_closure(graph, set(selected))
        if self.kind == "between":
            assert self.start is not None and self.end is not None
            validate_selection_target(graph, self.start)
            validate_selection_target(graph, self.end)
            started = False
            selected = []
            for name in names:
                if name == self.start:
                    started = True
                if started:
                    selected.append(name)
                if name == self.end:
                    break
            else:
                raise ValueError(
                    f"End step {self.end!r} does not appear after {self.start!r}"
                )
            return dependency_closure(graph, set(selected))
        if self.kind == "upstream_of":
            assert self.end is not None
            return run_one_selection(graph, self.end)
        if self.kind == "downstream_of":
            assert self.start is not None
            validate_selection_target(graph, self.start)
            consumers: dict[str, set[str]] = {n.name: set() for n in graph.nodes}
            for edge in graph.edges:
                consumers.setdefault(edge.producer_node, set()).add(edge.consumer_node)
            seen: set[str] = set()
            stack = [self.start]
            while stack:
                node = stack.pop()
                if node in seen:
                    continue
                seen.add(node)
                for downstream in consumers.get(node, ()):
                    if downstream not in seen:
                        stack.append(downstream)
            return tuple(n for n in names if n in seen)
        if self.kind == "matching":
            matched = [
                n.name
                for n in graph.nodes
                if self.tags & frozenset(n.metadata.get("tags", ()) or ())
            ]
            if not matched:
                return ()
            return dependency_closure(graph, set(matched))
        raise ValueError(f"Unknown selection kind {self.kind!r}")

    def to_plan_selection(self, graph: LogicalGraph) -> dict[str, Any]:
        """Convert to planner selection dict."""
        selected = self.resolve(graph)
        if self.kind == "until" and self.end is not None:
            return {"run_until": self.end}
        if self.kind in {"only", "upstream_of"} and len(self.nodes) == 1:
            return {"run_one": self.nodes[0]}
        if self.kind == "upstream_of" and self.end is not None:
            return {"run_one": self.end}
        return {"nodes": list(selected)}

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "nodes": list(self.nodes),
            "tags": sorted(self.tags),
            "start": self.start,
            "end": self.end,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RunSelection:
        """Decode a selection without silently dropping unknown fields."""
        allowed = {"kind", "nodes", "tags", "start", "end"}
        unknown = set(data) - allowed
        if unknown:
            raise ValueError(
                "Unknown run-selection field(s): " + ", ".join(sorted(unknown))
            )
        kind = data.get("kind", "all")
        nodes = data.get("nodes", ())
        tags = data.get("tags", ())
        if not isinstance(kind, str):
            raise TypeError("selection.kind must be a string")
        node_values = _string_values(nodes, name="selection.nodes")
        tag_values = _string_values(tags, name="selection.tags", allow_sets=True)
        start = data.get("start")
        end = data.get("end")
        if start is not None and not isinstance(start, str):
            raise TypeError("selection.start must be a string or null")
        if end is not None and not isinstance(end, str):
            raise TypeError("selection.end must be a string or null")
        return cls(
            kind=kind,
            nodes=node_values,
            tags=frozenset(tag_values),
            start=start,
            end=end,
        )


@dataclass(frozen=True, slots=True, init=False)
class RunRequest:
    """Portable request describing how to execute a pipeline."""

    selection: RunSelection
    intent: RunIntent
    materialization: MaterializationPolicy
    retry: RetryPolicy
    timeout: TimeoutPolicy
    cancellation: CancellationPolicy
    parameter_overrides: dict[str, dict[str, Any]]
    # Internal store; prefer ``asset_overrides``.
    binding_overrides: dict[str, str]
    implementation_overrides: dict[str, str]
    invalidation: InvalidationMode
    no_write: bool
    metadata: dict[str, Any]
    extensions: Mapping[str, Any]
    explicit_settings: frozenset[str]

    def __init__(
        self,
        selection: RunSelection | None = None,
        intent: RunIntent = RunIntent.STANDARD,
        materialization: MaterializationPolicy = MaterializationPolicy.DEFAULT,
        retry: RetryPolicy | None = None,
        timeout: TimeoutPolicy | None = None,
        cancellation: CancellationPolicy | None = None,
        parameter_overrides: Mapping[str, Mapping[str, Any]] | None = None,
        asset_overrides: dict[str, str] | None = None,
        implementation_overrides: Mapping[str, str] | None = None,
        invalidation: InvalidationMode = InvalidationMode.NONE,
        no_write: bool = False,
        metadata: Mapping[str, Any] | None = None,
        extensions: Mapping[str, Any] | None = None,
        explicit_settings: Iterable[str] | None = None,
        **kwargs: Any,
    ) -> None:
        if "binding_overrides" in kwargs:
            raise TypeError(
                "RunRequest(binding_overrides=...) was removed in ETLantic 0.16. "
                "Use asset_overrides= instead. "
                "See docs/11_DEVELOPMENT/MIGRATION_0_15_TO_0_16.md."
            )
        if kwargs:
            unknown = ", ".join(sorted(kwargs))
            raise TypeError(f"RunRequest got unexpected keyword argument(s): {unknown}")

        valid_explicit_settings: set[str] = {
            "retry.max_attempts",
            "retry.backoff_seconds",
            "retry.retry_on",
            "timeout.run_seconds",
            "timeout.step_seconds",
        }
        if explicit_settings is None:
            explicit: set[str] = set()
            if retry is not None:
                explicit.update(
                    {
                        "retry.max_attempts",
                        "retry.backoff_seconds",
                        "retry.retry_on",
                    }
                )
            if timeout is not None:
                explicit.update({"timeout.run_seconds", "timeout.step_seconds"})
        else:
            explicit = set()
            for key in cast(Iterable[object], explicit_settings):
                if not isinstance(key, str):
                    raise TypeError("explicit_settings must contain strings")
                explicit.add(key)
        unknown_explicit = explicit - valid_explicit_settings
        if unknown_explicit:
            raise ValueError(
                "Unknown explicit setting(s): " + ", ".join(sorted(unknown_explicit))
            )

        store = {str(k): str(v) for k, v in dict(asset_overrides or {}).items()}
        extension_data = cast(dict[str, Any], mutable_copy(extensions or {}))
        validate_extension_metadata(
            extension_data, path="run_request.extensions", strict=True
        )
        object.__setattr__(
            self,
            "selection",
            selection if selection is not None else RunSelection.all(),
        )
        object.__setattr__(self, "intent", intent)
        object.__setattr__(self, "materialization", materialization)
        object.__setattr__(self, "retry", retry if retry is not None else RetryPolicy())
        object.__setattr__(
            self, "timeout", timeout if timeout is not None else TimeoutPolicy()
        )
        object.__setattr__(
            self,
            "cancellation",
            cancellation if cancellation is not None else CancellationPolicy(),
        )
        object.__setattr__(
            self,
            "parameter_overrides",
            deepcopy(dict(parameter_overrides or {})),
        )
        object.__setattr__(self, "binding_overrides", store)
        object.__setattr__(
            self,
            "implementation_overrides",
            dict(implementation_overrides or {}),
        )
        object.__setattr__(self, "invalidation", invalidation)
        object.__setattr__(
            self,
            "no_write",
            True if intent is RunIntent.VALIDATE or no_write else no_write,
        )
        object.__setattr__(
            self,
            "metadata",
            mutable_copy(metadata or {}),
        )
        object.__setattr__(self, "extensions", deep_freeze(extension_data))
        object.__setattr__(self, "explicit_settings", frozenset(explicit))

    @property
    def asset_overrides(self) -> dict[str, str]:
        """Preferred public view of node → logical asset overrides."""
        return dict(self.binding_overrides)

    def to_dict(self) -> dict[str, Any]:
        overrides = dict(self.binding_overrides)
        return {
            "selection": self.selection.to_dict(),
            "intent": self.intent.value,
            "materialization": self.materialization.value,
            "retry": self.retry.to_dict(),
            "timeout": self.timeout.to_dict(),
            "cancellation": self.cancellation.to_dict(),
            "parameter_overrides": deepcopy(self.parameter_overrides),
            "asset_overrides": overrides,
            "implementation_overrides": mutable_copy(self.implementation_overrides),
            "invalidation": self.invalidation.value,
            "no_write": self.no_write,
            "metadata": deepcopy(self.metadata),
            "extensions": mutable_copy(self.extensions),
            "explicit_settings": sorted(self.explicit_settings),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RunRequest:
        """Decode a versioned run request, rejecting unrecognized semantics."""
        allowed = {
            "selection",
            "intent",
            "materialization",
            "retry",
            "timeout",
            "cancellation",
            "parameter_overrides",
            "asset_overrides",
            "implementation_overrides",
            "invalidation",
            "no_write",
            "metadata",
            "extensions",
            "explicit_settings",
        }
        unknown = set(data) - allowed
        if unknown:
            raise ValueError(
                "Unknown run-request field(s): " + ", ".join(sorted(unknown))
            )
        if "explicit_settings" not in data:
            raise ValueError("Missing required run-request field: explicit_settings")

        def mapping_value(
            name: str, default: Mapping[str, Any] | None = None
        ) -> Mapping[str, Any]:
            value: object = data.get(name, default or {})
            if not isinstance(value, Mapping):
                raise TypeError(f"{name} must be an object")
            return cast(Mapping[str, Any], value)

        def string_mapping(name: str) -> dict[str, str]:
            value = mapping_value(name)
            result: dict[str, str] = {}
            for key, item in cast(Mapping[object, object], value).items():
                if not isinstance(key, str) or not isinstance(item, str):
                    raise TypeError(f"{name} must map strings to strings")
                result[key] = item
            return result

        selection_data = mapping_value("selection")
        retry_data = mapping_value("retry")
        timeout_data = mapping_value("timeout")
        cancellation_data = mapping_value("cancellation")
        selection = RunSelection.from_dict(selection_data)

        retry_allowed = {"max_attempts", "backoff_seconds", "retry_on"}
        retry_unknown = set(retry_data) - retry_allowed
        if retry_unknown:
            raise ValueError(
                "Unknown retry field(s): " + ", ".join(sorted(retry_unknown))
            )
        max_attempts = retry_data.get("max_attempts", 1)
        backoff = retry_data.get("backoff_seconds", 0.0)
        retry_on_raw = retry_data.get("retry_on", ())
        if isinstance(max_attempts, bool) or not isinstance(max_attempts, int):
            raise TypeError("retry.max_attempts must be an integer")
        if isinstance(backoff, bool) or not isinstance(backoff, (int, float)):
            raise TypeError("retry.backoff_seconds must be a number")
        retry_on = _string_values(retry_on_raw, name="retry.retry_on")

        timeout_allowed = {"run_seconds", "step_seconds"}
        timeout_unknown = set(timeout_data) - timeout_allowed
        if timeout_unknown:
            raise ValueError(
                "Unknown timeout field(s): " + ", ".join(sorted(timeout_unknown))
            )
        run_seconds = timeout_data.get("run_seconds")
        step_seconds = timeout_data.get("step_seconds")
        for name, value in (
            ("run_seconds", run_seconds),
            ("step_seconds", step_seconds),
        ):
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, (int, float))
            ):
                raise TypeError(f"timeout.{name} must be a number or null")

        cancellation_allowed = {"cooperative", "abandon_after_seconds"}
        cancellation_unknown = set(cancellation_data) - cancellation_allowed
        if cancellation_unknown:
            raise ValueError(
                "Unknown cancellation field(s): "
                + ", ".join(sorted(cancellation_unknown))
            )
        cooperative = cancellation_data.get("cooperative", True)
        abandon_after = cancellation_data.get("abandon_after_seconds")
        if not isinstance(cooperative, bool):
            raise TypeError("cancellation.cooperative must be a boolean")
        if abandon_after is not None and (
            isinstance(abandon_after, bool)
            or not isinstance(abandon_after, (int, float))
        ):
            raise TypeError(
                "cancellation.abandon_after_seconds must be a number or null"
            )

        raw_parameters = mapping_value("parameter_overrides")
        parameters: dict[str, dict[str, Any]] = {}
        for key, value in cast(Mapping[object, object], raw_parameters).items():
            if not isinstance(key, str) or not isinstance(value, Mapping):
                raise TypeError("parameter_overrides must map strings to objects")
            values = cast(Mapping[object, Any], value)
            if not all(isinstance(name, str) for name in values):
                raise TypeError("parameter_overrides entries must use string keys")
            parameters[key] = {cast(str, name): item for name, item in values.items()}
        metadata = mapping_value("metadata")
        extensions = mapping_value("extensions")
        explicit_settings = set(
            _string_values(data["explicit_settings"], name="explicit_settings")
        )
        no_write = data.get("no_write", False)
        if not isinstance(no_write, bool):
            raise TypeError("no_write must be a boolean")

        intent = RunIntent(data.get("intent", RunIntent.STANDARD.value))
        materialization = MaterializationPolicy(
            data.get("materialization", MaterializationPolicy.DEFAULT.value)
        )
        invalidation = InvalidationMode(
            data.get("invalidation", InvalidationMode.NONE.value)
        )
        return cls(
            selection=selection,
            intent=intent,
            materialization=materialization,
            retry=RetryPolicy(
                max_attempts=max_attempts,
                backoff_seconds=float(backoff),
                retry_on=tuple(retry_on),
            ),
            timeout=TimeoutPolicy(
                run_seconds=float(run_seconds) if run_seconds is not None else None,
                step_seconds=float(step_seconds) if step_seconds is not None else None,
            ),
            cancellation=CancellationPolicy(
                cooperative=cooperative,
                abandon_after_seconds=(
                    float(abandon_after) if abandon_after is not None else None
                ),
            ),
            parameter_overrides=parameters,
            asset_overrides=string_mapping("asset_overrides"),
            implementation_overrides=string_mapping("implementation_overrides"),
            invalidation=invalidation,
            no_write=no_write,
            metadata=dict(metadata),
            extensions=dict(extensions),
            explicit_settings=explicit_settings,
        )


def resolve_request_policies(
    request: RunRequest,
    execution_settings: Mapping[str, Any],
    intents: Mapping[str, Any] | None = None,
) -> RunRequest:
    """Resolve profile policy defaults while preserving explicit request values.

    Request-level retry and timeout values take precedence field by field.
    Omitted fields inherit plan settings/intents, then use request defaults.
    ``explicit_settings`` preserves this distinction across the wire, including
    explicitly requested zero and ``None`` values.
    """
    intent_data = dict(intents or {})
    retry_intent_raw = intent_data.get("retry")
    timeout_intent_raw = intent_data.get("timeout")
    retry_intent: Mapping[str, Any] = (
        cast(Mapping[str, Any], retry_intent_raw)
        if isinstance(retry_intent_raw, Mapping)
        else {}
    )
    timeout_intent: Mapping[str, Any] = (
        cast(Mapping[str, Any], timeout_intent_raw)
        if isinstance(timeout_intent_raw, Mapping)
        else {}
    )

    def profile_value(
        setting_key: str,
        group: Mapping[str, Any],
        intent_key: str,
    ) -> Any:
        value = execution_settings.get(setting_key)
        if value is not None:
            return value
        value = group.get(intent_key)
        if value is not None:
            return value
        return None

    explicit = request.explicit_settings
    attempts_default = profile_value("retry_max_attempts", retry_intent, "max_attempts")
    attempts = (
        request.retry.max_attempts
        if "retry.max_attempts" in explicit
        else max(1, int(attempts_default))
        if attempts_default is not None
        else request.retry.max_attempts
    )

    backoff_default = profile_value(
        "retry_backoff_seconds",
        retry_intent,
        "backoff_seconds",
    )
    backoff = (
        request.retry.backoff_seconds
        if "retry.backoff_seconds" in explicit
        else float(backoff_default)
        if backoff_default is not None
        else request.retry.backoff_seconds
    )
    retry_on_default: Any = retry_intent.get("retry_on")
    retry_on = (
        request.retry.retry_on
        if "retry.retry_on" in explicit or retry_on_default is None
        else tuple(_string_values(retry_on_default, name="retry.retry_on"))
    )

    run_timeout_default = profile_value("timeout_seconds", timeout_intent, "seconds")
    run_timeout = (
        request.timeout.run_seconds
        if "timeout.run_seconds" in explicit
        else float(run_timeout_default)
        if run_timeout_default is not None
        else request.timeout.run_seconds
    )

    step_timeout_default = profile_value(
        "step_timeout_seconds",
        timeout_intent,
        "step_seconds",
    )
    step_timeout = (
        request.timeout.step_seconds
        if "timeout.step_seconds" in explicit
        else float(step_timeout_default)
        if step_timeout_default is not None
        else request.timeout.step_seconds
    )

    return RunRequest(
        selection=request.selection,
        intent=request.intent,
        materialization=request.materialization,
        retry=RetryPolicy(
            max_attempts=attempts,
            backoff_seconds=backoff,
            retry_on=tuple(retry_on),
        ),
        timeout=TimeoutPolicy(
            run_seconds=run_timeout,
            step_seconds=step_timeout,
        ),
        cancellation=request.cancellation,
        parameter_overrides=request.parameter_overrides,
        asset_overrides=request.asset_overrides,
        implementation_overrides=request.implementation_overrides,
        invalidation=request.invalidation,
        no_write=request.no_write,
        metadata=request.metadata,
        extensions=request.extensions,
        explicit_settings=explicit,
    )


def request_setting_provenance(
    request: RunRequest,
    execution_settings: Mapping[str, Any],
    *,
    profile_name: str,
    intents: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    """Return deterministic provenance for each effective request setting."""
    provenance = {
        f"execution_settings.{key}": f"profile:{profile_name}"
        for key in sorted(execution_settings)
    }
    intent_data = dict(intents or {})
    retry_intent_raw = intent_data.get("retry")
    timeout_intent_raw = intent_data.get("timeout")
    retry_intent: Mapping[str, Any] = (
        cast(Mapping[str, Any], retry_intent_raw)
        if isinstance(retry_intent_raw, Mapping)
        else {}
    )
    timeout_intent: Mapping[str, Any] = (
        cast(Mapping[str, Any], timeout_intent_raw)
        if isinstance(timeout_intent_raw, Mapping)
        else {}
    )

    def inherited(setting: str, nested: Any, legacy: str) -> bool:
        return (
            execution_settings.get(setting) is not None
            or nested is not None
            or intent_data.get(legacy) is not None
        )

    defaults = {
        "retry.max_attempts": inherited(
            "retry_max_attempts",
            retry_intent.get("max_attempts"),
            "retry_max_attempts",
        ),
        "retry.backoff_seconds": inherited(
            "retry_backoff_seconds",
            retry_intent.get("backoff_seconds"),
            "retry_backoff_seconds",
        ),
        "retry.retry_on": retry_intent.get("retry_on") is not None
        or intent_data.get("retry_on") is not None,
        "timeout.run_seconds": inherited(
            "timeout_seconds", timeout_intent.get("seconds"), "timeout_seconds"
        ),
        "timeout.step_seconds": inherited(
            "step_timeout_seconds",
            timeout_intent.get("step_seconds"),
            "step_timeout_seconds",
        ),
    }
    for key, from_profile in defaults.items():
        source = (
            "request"
            if key in request.explicit_settings
            else f"profile:{profile_name}"
            if from_profile
            else "runtime.default"
        )
        provenance[f"request.{key}"] = source

    provenance.update(
        {
            "request.selection": "request"
            if request.selection != RunSelection.all()
            else "runtime.default",
            "request.intent": "request"
            if request.intent is not RunIntent.STANDARD
            else "runtime.default",
            "request.materialization": "request"
            if request.materialization is not MaterializationPolicy.DEFAULT
            else "runtime.default",
            "request.cancellation": "request"
            if request.cancellation != CancellationPolicy()
            else "runtime.default",
            "request.parameter_overrides": "request"
            if request.parameter_overrides
            else "runtime.default",
            "request.asset_overrides": "request"
            if request.asset_overrides
            else "runtime.default",
            "request.implementation_overrides": "request"
            if request.implementation_overrides
            else "runtime.default",
            "request.invalidation": "request"
            if request.invalidation is not InvalidationMode.NONE
            else "runtime.default",
            "request.no_write": "request" if request.no_write else "runtime.default",
            "request.metadata": "request" if request.metadata else "runtime.default",
            "request.extensions": "request"
            if request.extensions
            else "runtime.default",
        }
    )
    return dict(sorted(provenance.items()))
