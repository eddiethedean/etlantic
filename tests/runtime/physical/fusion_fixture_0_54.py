"""Portable, schema-provable frozen scan/filter/project reference fixture."""

from typing import ClassVar

from pydantic import ConfigDict, create_model

from etlantic import (
    Data,
    Extract,
    Input,
    Load,
    Output,
    Parameter,
    Pipeline,
    Transformation,
)
from etlantic.transform import functions as F


class Raw(Data):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")
    key: int | None
    enabled: bool | None
    unused: int | None


class Selected(Data):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")
    key: int | None
    enabled: bool | None


class Result(Data):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")
    key: int | None


class Filter(Transformation):
    source: Input[Raw]
    key: Parameter[int] = 1
    result: Output[Raw]


@Filter.portable
def filter_rows(source, key):
    return source.filter(F.col("key") == key)


class Project(Transformation):
    source: Input[Raw]
    result: Output[Selected]


@Project.portable
def project(source):
    return source.select("key", "enabled")


class Consumer(Transformation):
    source: Input[Selected]
    result: Output[Result]


@Consumer.portable
def consume(source):
    return source.select("key")


class Reference(Pipeline):
    raw: Extract[Raw] = Extract(asset="raw")
    filtered = Filter.step(source=raw)
    projected = Project.step(source=filtered.result)
    consumer = Consumer.step(source=projected.result)
    out: Load[Result] = Load(input=consumer.result, asset="out")


MULTILINE_COLUMN = "key\nFILTER item"
MultilineRaw = create_model(
    "MultilineRaw",
    __base__=Data,
    __module__=__name__,
    __config__=ConfigDict(extra="ignore"),
    **{
        MULTILINE_COLUMN: (int | None, ...),
        "enabled": (bool | None, ...),
        "unused": (int | None, ...),
    },
)
MultilineSelected = create_model(
    "MultilineSelected",
    __base__=Data,
    __module__=__name__,
    __config__=ConfigDict(extra="ignore"),
    **{MULTILINE_COLUMN: (int | None, ...), "enabled": (bool | None, ...)},
)
MultilineResult = create_model(
    "MultilineResult",
    __base__=Data,
    __module__=__name__,
    __config__=ConfigDict(extra="ignore"),
    **{MULTILINE_COLUMN: (int | None, ...)},
)


class MultilineFilter(Transformation):
    source: Input[MultilineRaw]
    key: Parameter[int] = 1
    result: Output[MultilineRaw]


@MultilineFilter.portable
def multiline_filter(source, key):
    return source.filter(F.col(MULTILINE_COLUMN) == key)


class MultilineProject(Transformation):
    source: Input[MultilineRaw]
    result: Output[MultilineSelected]


@MultilineProject.portable
def multiline_project(source):
    return source.select(MULTILINE_COLUMN, "enabled")


class MultilineConsumer(Transformation):
    source: Input[MultilineSelected]
    result: Output[MultilineResult]


@MultilineConsumer.portable
def multiline_consume(source):
    return source.select(MULTILINE_COLUMN)


class MultilineReference(Pipeline):
    raw: Extract[MultilineRaw] = Extract(asset="raw")
    filtered = MultilineFilter.step(source=raw)
    projected = MultilineProject.step(source=filtered.result)
    consumer = MultilineConsumer.step(source=projected.result)
    out: Load[MultilineResult] = Load(input=consumer.result, asset="out")
