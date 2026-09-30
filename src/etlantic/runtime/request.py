"""RunIntent, RunSelection, RunRequest, and execution policies."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, cast

from etlantic.model import LogicalGraph
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
    BACKFILL = "backfill"
    REPLAY = "replay"


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

    def __init__(
        self,
        selection: RunSelection | None = None,
        intent: RunIntent = RunIntent.STANDARD,
        materialization: MaterializationPolicy = MaterializationPolicy.DEFAULT,
        retry: RetryPolicy | None = None,
        timeout: TimeoutPolicy | None = None,
        cancellation: CancellationPolicy | None = None,
        parameter_overrides: dict[str, dict[str, Any]] | None = None,
        asset_overrides: dict[str, str] | None = None,
        implementation_overrides: dict[str, str] | None = None,
        invalidation: InvalidationMode = InvalidationMode.NONE,
        no_write: bool = False,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        if "binding_overrides" in kwargs:
            raise TypeError(
                "RunRequest(binding_overrides=...) was removed in ETLantic 0.16. "
                "Use asset_overrides= instead. "
                "See docs/11_DEVELOPMENT/MIGRATION_0_15_TO_0_16.md."
            )
        store = {str(k): str(v) for k, v in dict(asset_overrides or {}).items()}
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
        object.__setattr__(self, "parameter_overrides", dict(parameter_overrides or {}))
        object.__setattr__(self, "binding_overrides", store)
        object.__setattr__(
            self, "implementation_overrides", dict(implementation_overrides or {})
        )
        object.__setattr__(self, "invalidation", invalidation)
        object.__setattr__(
            self,
            "no_write",
            True if intent is RunIntent.VALIDATE or no_write else no_write,
        )
        object.__setattr__(self, "metadata", dict(metadata or {}))

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
            "parameter_overrides": dict(self.parameter_overrides),
            "asset_overrides": overrides,
            "implementation_overrides": dict(self.implementation_overrides),
            "invalidation": self.invalidation.value,
            "no_write": self.no_write,
            "metadata": dict(self.metadata),
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
        }
        unknown = set(data) - allowed
        if unknown:
            raise ValueError(
                "Unknown run-request field(s): " + ", ".join(sorted(unknown))
            )

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
            parameters[key] = {
                cast(str, name): item for name, item in values.items()
            }
        metadata = mapping_value("metadata")
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
        )
