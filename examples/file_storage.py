"""Runnable JSON-to-JSON and CSV-to-CSV storage examples."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from etlantic import (
    Data,
    Extract,
    Input,
    Load,
    Output,
    Pipeline,
    PipelineRuntime,
    Transformation,
)
from etlantic.registry import BindingDescriptor, PlanningContext


class Row(Data):
    id: int
    name: str


class Normalize(Transformation):
    rows: Input[Row]
    result: Output[Row]


@Normalize.implementation("local")
def normalize(rows: list[Row]) -> list[Row]:
    return [Row(id=row.id, name=row.name.strip().title()) for row in rows]


class FilePipeline(Pipeline):
    source: Extract[Row] = Extract(asset="file_source")
    normalized = Normalize.step(rows=source)
    sink: Load[Row] = Load(input=normalized.result, asset="file_sink")


def run_files(source: Path, sink: Path, provider: str) -> object:
    context = PlanningContext.create(profile="development")
    context.registry.register_binding(
        BindingDescriptor(
            binding="file_source",
            provider=provider,
            location=str(source),
            kind="source",
        )
    )
    context.registry.register_binding(
        BindingDescriptor(
            binding="file_sink",
            provider=provider,
            location=str(sink),
            kind="sink",
        )
    )
    return FilePipeline.run(
        profile="development",
        runtime=PipelineRuntime(),
        context=context,
    )


def json_to_json(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / "input.json"
    sink = directory / "output.json"
    source.write_text(
        json.dumps([{"id": 1, "name": " ada "}, {"id": 2, "name": "grace"}]),
        encoding="utf-8",
    )
    run_files(source, sink, "json")
    return sink


def csv_to_csv(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / "input.csv"
    sink = directory / "output.csv"
    with source.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["id", "name"])
        writer.writeheader()
        writer.writerows([{"id": 1, "name": " ada "}, {"id": 2, "name": "grace"}])
    run_files(source, sink, "csv")
    return sink


if __name__ == "__main__":
    root = Path(__file__).resolve().parent / "_file_storage_out"
    json_out = json_to_json(root / "json")
    csv_out = csv_to_csv(root / "csv")
    print("json ->", json_out)
    print("csv ->", csv_out)
    print(json_out.read_text(encoding="utf-8"))
