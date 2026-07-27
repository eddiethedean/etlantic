"""Regression: PipelineDefinition.from_dict requires an explicit schema."""

from __future__ import annotations

import pytest
from examples.memory_customers import CustomerPipeline

from etlantic.authoring import PIPELINE_SCHEMA, definition_from_pipeline
from etlantic.authoring.definition import PipelineDefinition


def test_from_dict_requires_schema() -> None:
    data = definition_from_pipeline(CustomerPipeline).to_dict()
    data.pop("schema", None)
    with pytest.raises(KeyError, match="schema"):
        PipelineDefinition.from_dict(data)


def test_from_dict_accepts_explicit_schema() -> None:
    data = definition_from_pipeline(CustomerPipeline).to_dict()
    assert data["schema"] == PIPELINE_SCHEMA
    loaded = PipelineDefinition.from_dict(data)
    assert loaded.schema == PIPELINE_SCHEMA
