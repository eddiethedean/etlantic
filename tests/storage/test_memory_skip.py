"""Regression tests for in-memory skip write modes."""

from __future__ import annotations

import anyio
import pytest

from etlantic.storage import MemoryStorage


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
