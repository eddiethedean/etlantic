"""Deterministic ownership accounting for adaptive planning and projections.

Sizes are compact canonical UTF-8 sizes, never Python object sizes or RSS.
The sizing pass streams bounded chunks so it cannot allocate the buffer it is
trying to admit. A context-local ledger is shared by nested planner phases.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import MISSING, fields, is_dataclass
from typing import Any, TypeVar

from etlantic.diagnostics import Diagnostic, Severity, ValidationReport
from etlantic.exceptions import PipelineValidationError

MAX_TRANSIENT_BYTES = 256 * 1024 * 1024
T = TypeVar("T")
_ACTIVE: ContextVar[TransientBudget | None] = ContextVar(
    "adaptive_budget", default=None
)


def wire_view(value: Any) -> Any:
    """Borrow fields without copying their nested data or source definitions."""
    if isinstance(value, (set, frozenset)):
        return tuple(sorted(value))
    if is_dataclass(value) and not isinstance(value, type):
        excluded = {
            "Node": {"contract_type", "nested_graph"},
            "PortSpec": {"contract_type"},
            "ParameterSpec": {"value_type", "default", "value"},
        }.get(type(value).__name__, set())
        result = {
            f.name: getattr(value, f.name)
            for f in fields(value)
            if f.name not in excluded
        }
        if type(value).__name__ == "PhysicalUnit":
            result["schema"] = "etlantic.physical_unit/1"
        return result
    return value


class _RedactedMapping(Mapping):
    def __init__(self, value: Mapping) -> None:
        self.value = value

    def __iter__(self) -> Iterator:
        return iter(self.value)

    def __len__(self) -> int:
        return len(self.value)

    def __getitem__(self, key: Any) -> Any:
        return redacted_view(self.value[key])


class _RedactedSequence(Sequence):
    def __init__(self, value: Sequence) -> None:
        self.value = value

    def __len__(self) -> int:
        return len(self.value)

    def __getitem__(self, key: Any) -> Any:
        return redacted_view(self.value[key])


def redacted_view(value: Any) -> Any:
    """Borrow a path-redacted tree; never copy a registry payload to size it."""
    value = wire_view(value)
    if isinstance(value, str):
        if value.startswith(("/", "\\")) or (
            len(value) > 2 and value[1] == ":" and value[2] in {"/", "\\"}
        ):
            normalized = value.replace("\\", "/").rstrip("/")
            return "path:" + (normalized.rsplit("/", 1)[-1] or "root")
        return value
    if isinstance(value, Mapping):
        return _RedactedMapping(value)
    if isinstance(value, Sequence):
        return _RedactedSequence(value)
    return value


def canonical_chunks(value: Any) -> Iterator[bytes]:
    """Stream exactly json.dumps(sort_keys=True, ensure_ascii=False) compact bytes."""
    value = wire_view(value)
    if isinstance(value, str):
        yield b'"'
        for start in range(0, len(value), 4096):
            yield json.dumps(value[start : start + 4096], ensure_ascii=False)[
                1:-1
            ].encode("utf-8")
        yield b'"'
    elif isinstance(value, Mapping):
        yield b"{"
        for index, key in enumerate(sorted(value)):
            if index:
                yield b","
            yield from canonical_chunks(key)
            yield b":"
            yield from canonical_chunks(value[key])
        yield b"}"
    elif isinstance(value, Sequence):
        yield b"["
        for index, item in enumerate(value):
            if index:
                yield b","
            yield from canonical_chunks(item)
        yield b"]"
    else:
        yield json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )


def canonical_size(value: Any) -> int:
    return sum(len(chunk) for chunk in canonical_chunks(value))


def materialize_wire(value: Any) -> Any:
    """Copy a wire view only after its owner has reserved the complete size."""
    value = wire_view(value)
    if isinstance(value, Mapping):
        return {key: materialize_wire(value[key]) for key in sorted(value)}
    if isinstance(value, Sequence) and not isinstance(value, str):
        return [materialize_wire(item) for item in value]
    return value


def serialized_size(value: Any, indent: int | None = None, depth: int = 0) -> int:
    """Exact size for the public ensure_ascii=True JSON writer, before allocation."""
    value = wire_view(value)
    if isinstance(value, str):
        return 2 + sum(
            len(json.dumps(value[i : i + 4096])[1:-1])
            for i in range(0, len(value), 4096)
        )
    if isinstance(value, (Mapping, Sequence)):
        length = len(value)
        if not length:
            return 2
        mapping = isinstance(value, Mapping)
        values = value.items() if mapping else ((None, item) for item in value)
        size = 2 + max(0, length - 1)
        if indent is not None:
            size += length + 1 + max(0, indent) * ((depth + 1) * length + depth)
        for key, item in values:
            if mapping:
                size += serialized_size(key) + (1 if indent is None else 2)
            size += serialized_size(item, indent, depth + 1)
        return size
    return len(json.dumps(value))


class TransientBudget:
    """Request-owned ledger; reserve before constructing, release at last use."""

    def __init__(self, limit: int = MAX_TRANSIENT_BYTES) -> None:
        self.limit = limit
        self.live = 0
        self.peak = 0
        self.charges: dict[int, tuple[int, str]] = {}
        self.objects: dict[int, int] = {}
        self.categories: set[str] = set()
        self._next = 0

    def reserve(self, size: int, category: str) -> int:
        if size < 0:
            raise ValueError("negative adaptive allocation")
        if self.live + size > self.limit:
            diagnostic = Diagnostic(
                code="PMADP303",
                severity=Severity.ERROR,
                message=f"Adaptive transient budget exceeded in {category}.",
                path=("adaptive", "budget", category),
                phase="policy",
            )
            raise PipelineValidationError(
                f"PMADP303: {diagnostic.message}",
                report=ValidationReport.from_diagnostics(
                    [diagnostic], phases=("policy",)
                ),
            )
        self._next += 1
        self.charges[self._next] = (size, category)
        self.live += size
        self.peak = max(self.peak, self.live)
        self.categories.add(category)
        return self._next

    def release(self, token: int) -> None:
        size, _ = self.charges.pop(token)
        self.live -= size

    def release_object(self, value: Any) -> None:
        token = self.objects.pop(id(value), None)
        if token is not None:
            self.release(token)

    @contextmanager
    def allocation(
        self, value: Any, category: str, overhead: int = 0
    ) -> Iterator[None]:
        token = self.reserve(canonical_size(value) + overhead, category)
        try:
            yield
        finally:
            self.release(token)

    @contextmanager
    def frame(self) -> Iterator[None]:
        """Release temporary phase records while preserving the caller's owners."""
        before = set(self.charges)
        try:
            yield
        finally:
            for token in set(self.charges) - before:
                self.release(token)
            self.objects = {
                key: token
                for key, token in self.objects.items()
                if token in self.charges
            }


@contextmanager
def budget_scope(limit: int | None = None) -> Iterator[TransientBudget]:
    active = _ACTIVE.get()
    if active is not None:
        yield active
        return
    budget = TransientBudget(MAX_TRANSIENT_BYTES if limit is None else limit)
    token = _ACTIVE.set(budget)
    try:
        with budget.frame():
            yield budget
    finally:
        _ACTIVE.reset(token)


def current_budget() -> TransientBudget:
    budget = _ACTIVE.get()
    if budget is None:
        raise RuntimeError("adaptive budget scope required")
    return budget


def record(cls: type[T], category: str, **kwargs: Any) -> T:
    """Admit a record and its validation projection before constructing it."""
    payload = dict(kwargs)
    for field in fields(cls):  # type: ignore[arg-type]
        if field.name not in payload:
            if field.default is not MISSING:
                payload[field.name] = field.default
            elif field.default_factory is not MISSING:
                payload[field.name] = field.default_factory()
    if cls.__name__ == "PhysicalUnit":
        payload["schema"] = "etlantic.physical_unit/1"
    budget = current_budget()
    size = canonical_size(payload)
    token = budget.reserve(size + 64, category)
    try:
        with budget.allocation(payload, "validation-buffer"):
            result = cls(**kwargs)
    except BaseException:
        budget.release(token)
        raise
    budget.objects[id(result)] = token
    return result
