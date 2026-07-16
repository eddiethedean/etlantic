"""Storage binding unit tests."""

from __future__ import annotations

import json
from pathlib import Path

import anyio

from pipelantic import Data
from pipelantic.storage import CsvStorage, JsonStorage, MemoryStorage, NullStorage


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
