"""RunIntent, RunSelection, RunRequest, and execution policies."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from etlantic.model import LogicalGraph
from etlantic.plan.slicing import (
    dependency_closure,
    run_one_selection,
    run_until_selection,
    validate_selection_target,
)


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
        binding_overrides: dict[str, str] | None = None,
        asset_overrides: dict[str, str] | None = None,
        implementation_overrides: dict[str, str] | None = None,
        invalidation: InvalidationMode = InvalidationMode.NONE,
        no_write: bool = False,
        metadata: dict[str, Any] | None = None,
        *,
        _warn_legacy_overrides: bool = True,
    ) -> None:
        from etlantic._compat import warn_binding_overrides

        assets_map = {str(k): str(v) for k, v in dict(asset_overrides or {}).items()}
        bindings_map = {
            str(k): str(v) for k, v in dict(binding_overrides or {}).items()
        }
        if assets_map and bindings_map and assets_map != bindings_map:
            raise ValueError(
                "RunRequest asset_overrides and binding_overrides disagree. "
                "Provide only asset_overrides= (preferred) or identical maps."
            )
        if bindings_map and not assets_map and _warn_legacy_overrides:
            warn_binding_overrides(stacklevel=3)
        store = assets_map or bindings_map
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
            "binding_overrides": dict(overrides),
            "implementation_overrides": dict(self.implementation_overrides),
            "invalidation": self.invalidation.value,
            "no_write": self.no_write,
            "metadata": dict(self.metadata),
        }
