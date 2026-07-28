"""SparkForge-independent intermediate IR for migration mapping.

Medallion layer names live only in this adapter package — never in ETLantic core.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from etlantic.diagnostics import Diagnostic, Severity


class LayerKind(StrEnum):
    """SparkForge medallion layer (adapter-only vocabulary)."""

    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"


class StepKind(StrEnum):
    """SparkForge step kinds represented in the compatibility IR."""

    BRONZE_RULES = "bronze_rules"
    SILVER_TRANSFORM = "silver_transform"
    GOLD_TRANSFORM = "gold_transform"
    UNKNOWN = "unknown"


def _float_field(data: dict[str, Any], key: str, default: float) -> float:
    if key not in data or data[key] is None:
        return default
    return float(data[key])


@dataclass(frozen=True, slots=True)
class SparkForgeStepSpec:
    """One SparkForge step in secret-free form."""

    name: str
    kind: StepKind
    layer: LayerKind
    source: str | None = None
    table_name: str | None = None
    transform_ref: str | None = None
    rules: dict[str, Any] = field(default_factory=dict)
    write_mode: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind.value,
            "layer": self.layer.value,
            "source": self.source,
            "table_name": self.table_name,
            "transform_ref": self.transform_ref,
            "rules": dict(self.rules),
            "write_mode": self.write_mode,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        *,
        diagnostics: list[Diagnostic] | None = None,
    ) -> SparkForgeStepSpec:
        kind_raw = str(data.get("kind") or StepKind.UNKNOWN.value)
        try:
            kind = StepKind(kind_raw)
        except ValueError:
            kind = StepKind.UNKNOWN
        layer_raw = str(data.get("layer") or LayerKind.BRONZE.value)
        try:
            layer = LayerKind(layer_raw)
        except ValueError:
            layer = LayerKind.BRONZE
            if diagnostics is not None:
                diagnostics.append(
                    Diagnostic(
                        code="PMSF308",
                        severity=Severity.WARNING,
                        message=(
                            f"Unknown SparkForge layer {layer_raw!r} on step "
                            f"{data.get('name')!r}; coerced to bronze."
                        ),
                        path=("steps", str(data.get("name") or "?"), "layer"),
                        phase="sparkforge_adapter",
                    )
                )
        return cls(
            name=str(data["name"]),
            kind=kind,
            layer=layer,
            source=data.get("source"),
            table_name=data.get("table_name"),
            transform_ref=data.get("transform_ref"),
            rules=dict(data.get("rules") or {}),
            write_mode=data.get("write_mode"),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True, slots=True)
class SparkForgePipelineSpec:
    """Complete SparkForge pipeline description (fixture-friendly)."""

    name: str
    schema: str = "default"
    steps: tuple[SparkForgeStepSpec, ...] = ()
    min_bronze_rate: float = 90.0
    min_silver_rate: float = 95.0
    min_gold_rate: float = 98.0
    engine: str = "spark"
    legacy_engine_extensions: tuple[str, ...] = ()
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
            "legacy_engine_extensions": list(self.legacy_engine_extensions),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        *,
        diagnostics: list[Diagnostic] | None = None,
    ) -> SparkForgePipelineSpec:
        steps_raw = data.get("steps") or ()
        steps_list: list[SparkForgeStepSpec] = []
        for index, item in enumerate(steps_raw):
            if not isinstance(item, dict):
                if diagnostics is not None:
                    diagnostics.append(
                        Diagnostic(
                            code="PMSF309",
                            severity=Severity.WARNING,
                            message=(
                                f"Ignoring non-dict SparkForge step at index {index}."
                            ),
                            path=("steps", str(index)),
                            phase="sparkforge_adapter",
                        )
                    )
                continue
            name = item.get("name")
            if name is None or not str(name).strip():
                if diagnostics is not None:
                    diagnostics.append(
                        Diagnostic(
                            code="PMSF310",
                            severity=Severity.ERROR,
                            message=(
                                f"SparkForge step at index {index} is missing a name."
                            ),
                            path=("steps", str(index), "name"),
                            phase="sparkforge_adapter",
                        )
                    )
                continue
            steps_list.append(
                SparkForgeStepSpec.from_dict(item, diagnostics=diagnostics)
            )
        return cls(
            name=str(data.get("name") or "AdaptedPipeline"),
            schema=str(data.get("schema") or "default"),
            steps=tuple(steps_list),
            min_bronze_rate=_float_field(data, "min_bronze_rate", 90.0),
            min_silver_rate=_float_field(data, "min_silver_rate", 95.0),
            min_gold_rate=_float_field(data, "min_gold_rate", 98.0),
            engine=str(data.get("engine") or "spark"),
            legacy_engine_extensions=tuple(
                str(x) for x in (data.get("legacy_engine_extensions") or ())
            ),
            metadata=dict(data.get("metadata") or {}),
        )

    @classmethod
    def parse(
        cls, data: dict[str, Any]
    ) -> tuple[SparkForgePipelineSpec, list[Diagnostic]]:
        """Parse IR and return any coercion / hygiene diagnostics."""
        diagnostics: list[Diagnostic] = []
        return cls.from_dict(data, diagnostics=diagnostics), diagnostics
