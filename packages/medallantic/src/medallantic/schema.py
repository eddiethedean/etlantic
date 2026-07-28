"""Facade-owned medallion document schema (not an ETLantic wire schema)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class MedallionStep:
    """One bronze, silver, or gold step in a medallion document."""

    name: str
    layer: str  # bronze | silver | gold
    kind: str  # bronze_rules | silver_transform | gold_transform
    source: str | None = None
    asset: str | None = None
    transform_ref: str | None = None
    rules: dict[str, Any] = field(default_factory=dict)
    write_mode: str | None = None
    description: str | None = None
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "layer": self.layer,
            "kind": self.kind,
            "source": self.source,
            "asset": self.asset,
            "transform_ref": self.transform_ref,
            "rules": dict(self.rules),
            "write_mode": self.write_mode,
            "description": self.description,
            "tags": list(self.tags),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MedallionStep:
        tags_raw = data.get("tags") or ()
        return cls(
            name=str(data["name"]),
            layer=str(data.get("layer") or "bronze"),
            kind=str(data.get("kind") or "bronze_rules"),
            source=(str(data["source"]) if data.get("source") is not None else None),
            asset=(str(data["asset"]) if data.get("asset") is not None else None),
            transform_ref=(
                str(data["transform_ref"])
                if data.get("transform_ref") is not None
                else None
            ),
            rules=dict(data.get("rules") or {}),
            write_mode=(
                str(data["write_mode"]) if data.get("write_mode") is not None else None
            ),
            description=(
                str(data["description"])
                if data.get("description") is not None
                else None
            ),
            tags=tuple(str(t) for t in tags_raw),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True, slots=True)
class MedallionDocument:
    """Declarative medallion pipeline document owned by Medallantic."""

    name: str
    schema: str = "default"
    steps: tuple[MedallionStep, ...] = ()
    min_bronze_rate: float = 90.0
    min_silver_rate: float = 95.0
    min_gold_rate: float = 98.0
    engine: str = "local"
    description: str | None = None
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "schema": self.schema,
            "steps": [s.to_dict() for s in self.steps],
            "min_bronze_rate": self.min_bronze_rate,
            "min_silver_rate": self.min_silver_rate,
            "min_gold_rate": self.min_gold_rate,
            "engine": self.engine,
            "description": self.description,
            "tags": list(self.tags),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MedallionDocument:
        steps_raw = data.get("steps") or ()
        tags_raw = data.get("tags") or ()
        return cls(
            name=str(data["name"]),
            schema=str(data.get("schema") or "default"),
            steps=tuple(
                MedallionStep.from_dict(s) if isinstance(s, dict) else s
                for s in steps_raw
            ),
            min_bronze_rate=_float_field(data, "min_bronze_rate", 90.0),
            min_silver_rate=_float_field(data, "min_silver_rate", 95.0),
            min_gold_rate=_float_field(data, "min_gold_rate", 98.0),
            engine=str(data.get("engine") or "local"),
            description=(
                str(data["description"])
                if data.get("description") is not None
                else None
            ),
            tags=tuple(str(t) for t in tags_raw),
            metadata=dict(data.get("metadata") or {}),
        )


def _float_field(data: dict[str, Any], key: str, default: float) -> float:
    """Parse a float, preserving explicit ``0.0`` (unlike ``or default``)."""
    if key not in data or data[key] is None:
        return default
    return float(data[key])
