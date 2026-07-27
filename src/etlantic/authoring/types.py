"""Shared types for definition-aware lifecycle entry points."""

from __future__ import annotations

from typing import Any, TypeAlias

from etlantic.authoring.definition import PipelineDefinition
from etlantic.pipeline import Pipeline

PipelineLike: TypeAlias = type[Pipeline] | PipelineDefinition


def is_pipeline_definition(obj: Any) -> bool:
    return isinstance(obj, PipelineDefinition)


def is_pipeline_class(obj: Any) -> bool:
    return isinstance(obj, type) and issubclass(obj, Pipeline)


def coerce_definition(pipeline: PipelineLike) -> PipelineDefinition:
    """Return a PipelineDefinition for a class or definition input."""
    if isinstance(pipeline, PipelineDefinition):
        return pipeline
    from etlantic.authoring.normalize import definition_from_pipeline

    return definition_from_pipeline(pipeline)


def pipeline_display_name(pipeline: PipelineLike) -> str:
    if isinstance(pipeline, PipelineDefinition):
        return pipeline.pipeline_name
    return pipeline.__name__
