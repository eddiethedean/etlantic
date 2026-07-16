"""In-run artifact store realizing plan ArtifactStrategy."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pipelantic.plan.artifacts import ArtifactRef, ArtifactStrategy
from pipelantic.storage.protocol import as_records, records_to_dicts


@dataclass
class ArtifactStore:
    """Holds run artifacts in memory and optional durable workspace files.

    Native dataframe handles are stored as-is. Durable serialization still
    requires collectible records; callers must collect LazyFrames before
    requesting durable storage.
    """

    workspace: Path | None = None
    _values: dict[str, Any] = field(default_factory=dict)
    _refs: dict[str, ArtifactRef] = field(default_factory=dict)
    _ownership: dict[str, str] = field(default_factory=dict)

    def put(
        self,
        ref: ArtifactRef,
        value: Any,
        *,
        durable: bool = False,
        ownership: str | None = None,
    ) -> None:
        self._refs[ref.identity] = ref
        self._values[ref.identity] = value
        # Also index by logical output for easy lookup.
        self._values[ref.logical_output] = value
        self._refs[ref.logical_output] = ref
        if ownership is not None:
            self._ownership[ref.identity] = ownership
            self._ownership[ref.logical_output] = ownership
        if durable and self.workspace is not None:
            self.workspace.mkdir(parents=True, exist_ok=True)
            path = (
                self.workspace
                / f"{ref.identity.replace(':', '_').replace('/', '_')}.json"
            )
            path.write_text(
                json.dumps(records_to_dicts(value), indent=2, sort_keys=True),
                encoding="utf-8",
            )
            self._values[ref.identity] = value

    def get_raw(self, key: str) -> Any:
        """Return the stored handle without record conversion."""
        if key not in self._values:
            raise KeyError(f"Artifact not found: {key}")
        return self._values[key]

    def get(self, key: str, *, contract_type: type[Any] | None = None) -> Any:
        """Return records when possible; otherwise the raw handle."""
        value = self.get_raw(key)
        # Preserve native frames / lazy handles for dataframe engines.
        if _looks_like_frame(value):
            return value
        return as_records(value, contract_type)

    def ownership(self, key: str) -> str | None:
        return self._ownership.get(key)

    def has(self, key: str) -> bool:
        return key in self._values

    def invalidate(self, keys: set[str]) -> None:
        for key in list(self._values):
            if key in keys:
                self._values.pop(key, None)
                self._refs.pop(key, None)
                self._ownership.pop(key, None)

    def clear(self) -> None:
        self._values.clear()
        self._refs.clear()
        self._ownership.clear()

    def list_refs(self) -> tuple[ArtifactRef, ...]:
        seen: set[str] = set()
        out: list[ArtifactRef] = []
        for ref in self._refs.values():
            if ref.identity in seen:
                continue
            seen.add(ref.identity)
            out.append(ref)
        return tuple(out)

    def should_durable(self, strategy: ArtifactStrategy | str) -> bool:
        value = strategy.value if isinstance(strategy, ArtifactStrategy) else strategy
        return value == ArtifactStrategy.DURABLE.value


def _looks_like_frame(value: Any) -> bool:
    if value is None or isinstance(
        value, (list, tuple, dict, str, bytes, int, float, bool)
    ):
        return False
    module = type(value).__module__ or ""
    name = type(value).__name__
    if module.startswith("polars") or module.startswith("pandas"):
        return True
    return name in {"DataFrame", "LazyFrame", "Series"}
