# pyright: reportMissingTypeArgument=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportUnknownVariableType=false
"""Storage binding unit tests."""

from __future__ import annotations

import json
from pathlib import Path

import anyio
import pytest

from etlantic import Data
from etlantic.storage import CsvStorage, JsonStorage, MemoryStorage, NullStorage


class Item(Data):
    id: int
    label: str


def test_memory_seed_round_trip() -> None:
    store = MemoryStorage()

    async def _run() -> None:
        store.seed("items", [Item(id=1, label="a")])
        rows = await store.read(
            binding="items", location=None, contract_type=Item, context={}
        )
        assert rows[0].label == "a"
        await store.write(
            binding="out",
            location=None,
            data=[Item(id=2, label="b")],
            contract_type=Item,
            context={},
        )
        assert store.get("out")[0].id == 2

    anyio.run(_run)


@pytest.mark.parametrize("write_mode", ("skip_if_exists", "skip"))
@pytest.mark.parametrize("location", (None, "output-location"))
@pytest.mark.parametrize(
    ("initial_data", "expected_data", "skipped"),
    (
        (None, [{"id": 2}], False),
        ([], [], True),
        ([{"id": 1}], [{"id": 1}], True),
    ),
)
def test_memory_skip_write_modes_respect_dataset_existence(
    write_mode: str,
    location: str | None,
    initial_data: list[dict[str, int]] | None,
    expected_data: list[dict[str, int]],
    skipped: bool,
) -> None:
    store = MemoryStorage()
    if initial_data is not None:
        store.seed("out", initial_data, location=location)

    async def _write() -> dict[str, object]:
        return await store.write(
            binding="out",
            location=location,
            data=[{"id": 2}],
            contract_type=None,
            context={"write_mode": write_mode},
        )

    receipt = anyio.run(_write)

    assert receipt["skipped"] is skipped
    assert receipt["records"] == len(expected_data)
    assert store.get("out", location=location) == expected_data


def test_json_and_csv(tmp_path: Path) -> None:
    json_path = tmp_path / "data.json"
    csv_path = tmp_path / "data.csv"
    json_store = JsonStorage()
    csv_store = CsvStorage()

    async def _run() -> None:
        await json_store.write(
            binding="j",
            location=str(json_path),
            data=[Item(id=1, label="x")],
            contract_type=Item,
            context={},
        )
        rows = await json_store.read(
            binding="j",
            location=str(json_path),
            contract_type=Item,
            context={},
        )
        assert rows[0].label == "x"
        await csv_store.write(
            binding="c",
            location=str(csv_path),
            data=rows,
            contract_type=Item,
            context={},
        )
        assert "id,label" in csv_path.read_text(encoding="utf-8")

    anyio.run(_run)
    assert json.loads(json_path.read_text(encoding="utf-8"))[0]["id"] == 1


def test_null_discards_writes() -> None:
    store = NullStorage()

    async def _run() -> dict:
        return await store.write(
            binding="x",
            location=None,
            data=[Item(id=1, label="z")],
            contract_type=Item,
            context={},
        )

    result = anyio.run(_run)
    assert result["written"] is False
