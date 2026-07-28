"""Fluent MedallionBuilder for native medallion authoring."""

from __future__ import annotations

from typing import Any, Self

from etlantic.authoring.definition import PipelineDefinition
from etlantic.authoring.serialize import pipeline_fingerprint
from medallantic.authoring import from_document
from medallantic.lower import LoweringResult, lower_document
from medallantic.schema import MedallionDocument, MedallionStep


class MedallionBuilder:
    """Fluent builder that produces a ``MedallionDocument`` / definition."""

    def __init__(
        self,
        name: str,
        *,
        schema: str = "default",
        engine: str = "local",
        description: str | None = None,
        tags: tuple[str, ...] | list[str] | None = None,
        min_bronze_rate: float = 90.0,
        min_silver_rate: float = 95.0,
        min_gold_rate: float = 98.0,
    ) -> None:
        self._name = name
        self._schema = schema
        self._engine = engine
        self._description = description
        self._tags = tuple(tags or ())
        self._min_bronze_rate = min_bronze_rate
        self._min_silver_rate = min_silver_rate
        self._min_gold_rate = min_gold_rate
        self._steps: list[MedallionStep] = []
        self._metadata: dict[str, Any] = {}

    def bronze(
        self,
        name: str,
        *,
        asset: str | None = None,
        rules: dict[str, Any] | None = None,
        description: str | None = None,
        tags: tuple[str, ...] | list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Self:
        self._steps.append(
            MedallionStep(
                name=name,
                layer="bronze",
                kind="bronze_rules",
                asset=asset or name,
                rules=dict(rules or {}),
                description=description,
                tags=tuple(tags or ()),
                metadata=dict(metadata or {}),
            )
        )
        return self

    def silver(
        self,
        name: str,
        *,
        source: str,
        asset: str | None = None,
        write_mode: str = "overwrite",
        transform_ref: str | None = None,
        description: str | None = None,
        tags: tuple[str, ...] | list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Self:
        self._steps.append(
            MedallionStep(
                name=name,
                layer="silver",
                kind="silver_transform",
                source=source,
                asset=asset or name,
                write_mode=write_mode,
                transform_ref=transform_ref,
                description=description,
                tags=tuple(tags or ()),
                metadata=dict(metadata or {}),
            )
        )
        return self

    def gold(
        self,
        name: str,
        *,
        source: str,
        asset: str | None = None,
        write_mode: str = "overwrite",
        transform_ref: str | None = None,
        description: str | None = None,
        tags: tuple[str, ...] | list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Self:
        self._steps.append(
            MedallionStep(
                name=name,
                layer="gold",
                kind="gold_transform",
                source=source,
                asset=asset or name,
                write_mode=write_mode,
                transform_ref=transform_ref,
                description=description,
                tags=tuple(tags or ()),
                metadata=dict(metadata or {}),
            )
        )
        return self

    def with_metadata(self, **metadata: Any) -> Self:
        self._metadata.update(metadata)
        return self

    def to_document(self) -> MedallionDocument:
        return MedallionDocument(
            name=self._name,
            schema=self._schema,
            steps=tuple(self._steps),
            min_bronze_rate=self._min_bronze_rate,
            min_silver_rate=self._min_silver_rate,
            min_gold_rate=self._min_gold_rate,
            engine=self._engine,
            description=self._description,
            tags=self._tags,
            metadata=dict(self._metadata),
        )

    def lower(self) -> LoweringResult:
        return lower_document(self.to_document())

    def build(self) -> PipelineDefinition:
        """Build a sealed public ``PipelineDefinition``."""
        defn = self.lower().definition
        return defn.with_fingerprint(pipeline_fingerprint(defn))

    def as_pipeline(self) -> type:
        """Return a ``MedallionPipeline`` subclass for class-style use."""
        return from_document(self.to_document())
