"""Native MedallionPipeline class authoring surfaces."""

from __future__ import annotations

from typing import Any, ClassVar

from etlantic.authoring.definition import PipelineDefinition
from etlantic.authoring.serialize import pipeline_fingerprint
from medallantic.lower import LoweringResult, lower_document
from medallantic.schema import MedallionDocument, MedallionStep


class LayerStep:
    """Base descriptor for bronze/silver/gold class attributes."""

    layer: ClassVar[str]
    default_kind: ClassVar[str]

    def __init__(
        self,
        *,
        asset: str | None = None,
        source: str | None = None,
        write_mode: str | None = None,
        transform_ref: str | None = None,
        rules: dict[str, Any] | None = None,
        description: str | None = None,
        tags: tuple[str, ...] | list[str] | None = None,
        kind: str | None = None,
        metadata: dict[str, Any] | None = None,
        name: str | None = None,
    ) -> None:
        self.asset = asset
        self.source = source
        self.write_mode = write_mode
        self.transform_ref = transform_ref
        self.rules = dict(rules or {})
        self.description = description
        self.tags = tuple(tags or ())
        self.kind = kind or self.default_kind
        self.metadata = dict(metadata or {})
        self.name = name

    def to_step(self, name: str) -> MedallionStep:
        return MedallionStep(
            name=self.name or name,
            layer=self.layer,
            kind=self.kind,
            source=self.source,
            asset=self.asset,
            transform_ref=self.transform_ref,
            rules=dict(self.rules),
            write_mode=self.write_mode,
            description=self.description,
            tags=self.tags,
            metadata=dict(self.metadata),
        )


class Bronze(LayerStep):
    """Bronze ingest step (maps to an ETLantic Extract source)."""

    layer = "bronze"
    default_kind = "bronze_rules"


class Silver(LayerStep):
    """Silver transform step (maps to step + optional sink)."""

    layer = "silver"
    default_kind = "silver_transform"

    def __init__(
        self, *, source: str, write_mode: str = "overwrite", **kwargs: Any
    ) -> None:
        super().__init__(source=source, write_mode=write_mode, **kwargs)


class Gold(LayerStep):
    """Gold publish step (maps to step + optional sink)."""

    layer = "gold"
    default_kind = "gold_transform"

    def __init__(
        self, *, source: str, write_mode: str = "overwrite", **kwargs: Any
    ) -> None:
        super().__init__(source=source, write_mode=write_mode, **kwargs)


class MedallionPipeline:
    """Class-style native medallion authoring.

    Subclass and declare ``Bronze`` / ``Silver`` / ``Gold`` attributes, then call
    ``to_definition()`` or ``lower()``.
    """

    __medallion_name__: ClassVar[str | None] = None
    __medallion_schema__: ClassVar[str] = "default"
    __medallion_engine__: ClassVar[str] = "local"
    __medallion_description__: ClassVar[str | None] = None
    __medallion_tags__: ClassVar[tuple[str, ...]] = ()
    __min_bronze_rate__: ClassVar[float] = 90.0
    __min_silver_rate__: ClassVar[float] = 95.0
    __min_gold_rate__: ClassVar[float] = 98.0

    @classmethod
    def _collect_steps(cls) -> tuple[MedallionStep, ...]:
        steps: list[MedallionStep] = []
        for base in reversed(cls.__mro__):
            for key, value in vars(base).items():
                if key.startswith("_"):
                    continue
                if isinstance(value, LayerStep):
                    steps.append(value.to_step(key))
        # Last declaration wins on duplicate names (subclass overrides).
        by_name: dict[str, MedallionStep] = {}
        for step in steps:
            by_name[step.name] = step
        return tuple(by_name.values())

    @classmethod
    def to_document(cls) -> MedallionDocument:
        """Return the facade-owned medallion document for this class."""
        return MedallionDocument(
            name=cls.__medallion_name__ or cls.__name__,
            schema=cls.__medallion_schema__,
            steps=cls._collect_steps(),
            min_bronze_rate=cls.__min_bronze_rate__,
            min_silver_rate=cls.__min_silver_rate__,
            min_gold_rate=cls.__min_gold_rate__,
            engine=cls.__medallion_engine__,
            description=cls.__medallion_description__,
            tags=cls.__medallion_tags__,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> type[MedallionPipeline]:
        """Build an anonymous MedallionPipeline subclass from a document dict."""
        doc = MedallionDocument.from_dict(data)
        return from_document(doc)

    @classmethod
    def lower(cls) -> LoweringResult:
        """Lower this pipeline onto ETLantic Pipeline / definition surfaces."""
        return lower_document(cls.to_document())

    @classmethod
    def to_definition(cls) -> PipelineDefinition:
        """Return a sealed public ``PipelineDefinition``."""
        defn = cls.lower().definition
        return defn.with_fingerprint(pipeline_fingerprint(defn))


def from_document(doc: MedallionDocument) -> type[MedallionPipeline]:
    """Create an anonymous ``MedallionPipeline`` subclass from a document."""
    ns: dict[str, Any] = {
        "__medallion_name__": doc.name,
        "__medallion_schema__": doc.schema,
        "__medallion_engine__": doc.engine,
        "__medallion_description__": doc.description,
        "__medallion_tags__": doc.tags,
        "__min_bronze_rate__": doc.min_bronze_rate,
        "__min_silver_rate__": doc.min_silver_rate,
        "__min_gold_rate__": doc.min_gold_rate,
    }
    for step in doc.steps:
        layer_cls: type[LayerStep]
        if step.layer == "bronze":
            layer_cls = Bronze
            ns[step.name] = layer_cls(
                asset=step.asset,
                source=step.source,
                write_mode=step.write_mode,
                transform_ref=step.transform_ref,
                rules=step.rules,
                description=step.description,
                tags=step.tags,
                kind=step.kind,
                metadata=step.metadata,
                name=step.name,
            )
        elif step.layer == "silver":
            layer_cls = Silver
            ns[step.name] = layer_cls(
                asset=step.asset,
                source=step.source or "",
                write_mode=step.write_mode or "overwrite",
                transform_ref=step.transform_ref,
                rules=step.rules,
                description=step.description,
                tags=step.tags,
                kind=step.kind,
                metadata=step.metadata,
                name=step.name,
            )
        else:
            layer_cls = Gold
            ns[step.name] = layer_cls(
                asset=step.asset,
                source=step.source or "",
                write_mode=step.write_mode or "overwrite",
                transform_ref=step.transform_ref,
                rules=step.rules,
                description=step.description,
                tags=step.tags,
                kind=step.kind,
                metadata=step.metadata,
                name=step.name,
            )
    return type(f"{_safe(doc.name)}Medallion", (MedallionPipeline,), ns)


def _safe(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in name)
    return cleaned or "Pipeline"
