"""Regression coverage for CSV append header alignment."""

from __future__ import annotations

from pathlib import Path

import anyio
import pytest

from etlantic.storage import CsvStorage


def test_csv_append_uses_existing_header_order(tmp_path: Path) -> None:
    path = tmp_path / "rows.csv"
    store = CsvStorage()

    async def exercise() -> None:
        args = {"binding": "rows", "location": str(path), "contract_type": None}
        await store.write(**args, data=[{"id": 1, "amount": 100}], context={})
        await store.write(
            **args,
            data=[{"amount": 200, "id": 2}],
            context={"write_mode": "append"},
        )
        rows = await store.read(**args, context={})
        assert rows == [
            {"id": "1", "amount": "100"},
            {"id": "2", "amount": "200"},
        ]

    anyio.run(exercise)


def test_csv_append_rejects_incompatible_fields_before_mutation(tmp_path: Path) -> None:
    path = tmp_path / "rows.csv"
    store = CsvStorage()
    initial = "id,amount\n1,100\n"
    path.write_text(initial, encoding="utf-8")

    async def exercise() -> None:
        with pytest.raises(ValueError, match="match the existing file header"):
            await store.write(
                binding="rows",
                location=str(path),
                data=[{"amount": 200, "other": 2}],
                contract_type=None,
                context={"write_mode": "append"},
            )

    anyio.run(exercise)
    assert path.read_text(encoding="utf-8") == initial
