"""Keep public examples executable."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from etlantic.runtime.state import RunStatus


def test_memory_customers_example() -> None:
    path = Path(__file__).parents[1] / "examples" / "memory_customers.py"
    spec = importlib.util.spec_from_file_location("etlantic_memory_customers", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    runtime, report = module.run_example()

    assert report.status is RunStatus.SUCCEEDED
    assert [
        customer.model_dump() for customer in runtime.memory.get("customer_sink")
    ] == [
        {"customer_id": 1, "full_name": "Ada Lovelace"},
        {"customer_id": 2, "full_name": "Grace Hopper"},
    ]


def test_file_storage_examples(tmp_path: Path) -> None:
    path = Path(__file__).parents[1] / "examples" / "file_storage.py"
    spec = importlib.util.spec_from_file_location("etlantic_file_storage", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    json_output = module.json_to_json(tmp_path / "json")
    csv_output = module.csv_to_csv(tmp_path / "csv")

    assert json.loads(json_output.read_text(encoding="utf-8"))[0]["name"] == "Ada"
    assert "Ada" in csv_output.read_text(encoding="utf-8")
