"""Regression coverage for SafeIoPolicy enforcement in file bindings."""

from __future__ import annotations

from pathlib import Path

import anyio
import pytest

from etlantic.io_policy import SafeIoPolicy
from etlantic.storage import CsvStorage, JsonStorage


@pytest.mark.parametrize(
    ("store", "suffix", "content"),
    [
        (JsonStorage(), ".json", '[{"id": 1}]\n'),
        (CsvStorage(), ".csv", "id\n1\n"),
    ],
)
def test_file_reads_honor_safe_io_byte_budget(
    tmp_path: Path, store: object, suffix: str, content: str
) -> None:
    path = tmp_path / f"input{suffix}"
    path.write_text(content, encoding="utf-8")
    policy = SafeIoPolicy.for_root(tmp_path, max_read_bytes=1)

    async def exercise() -> None:
        with pytest.raises(Exception, match="oversized"):
            await store.read(  # type: ignore[attr-defined]
                binding="input",
                location=str(path),
                contract_type=None,
                context={"safe_io": policy, "run_id": "read-budget"},
            )

    anyio.run(exercise)


@pytest.mark.parametrize(
    ("store", "suffix", "initial", "rows"),
    [
        (JsonStorage(), ".json", '[{"id": 1}]\n', [{"id": 2}]),
        (CsvStorage(), ".csv", "id\n1\n", [{"id": 2}]),
    ],
)
def test_file_writes_honor_safe_io_reject_policy(
    tmp_path: Path,
    store: object,
    suffix: str,
    initial: str,
    rows: list[dict[str, int]],
) -> None:
    path = tmp_path / f"output{suffix}"
    path.write_text(initial, encoding="utf-8")
    policy = SafeIoPolicy.for_root(tmp_path, overwrite_policy="reject")

    async def exercise() -> None:
        with pytest.raises(Exception, match="Overwrite rejected"):
            await store.write(  # type: ignore[attr-defined]
                binding="output",
                location=str(path),
                data=rows,
                contract_type=None,
                context={"safe_io": policy, "run_id": "reject-write"},
            )

    anyio.run(exercise)
    assert path.read_text(encoding="utf-8") == initial


def test_csv_serializes_the_complete_batch_before_mutation(tmp_path: Path) -> None:
    path = tmp_path / "output.csv"
    initial = "id,amount\n99,999\n"
    path.write_text(initial, encoding="utf-8")
    policy = SafeIoPolicy.for_root(tmp_path)

    async def exercise() -> None:
        with pytest.raises(ValueError, match="dict contains fields not in fieldnames"):
            await CsvStorage().write(
                binding="output",
                location=str(path),
                data=[{"id": 1, "amount": 100}, {"id": 2, "extra": 200}],
                contract_type=None,
                context={"safe_io": policy, "run_id": "atomic-csv"},
            )

    anyio.run(exercise)
    assert path.read_text(encoding="utf-8") == initial
