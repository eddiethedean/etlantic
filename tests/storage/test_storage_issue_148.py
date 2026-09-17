"""Regression coverage for SafeIoPolicy enforcement in file bindings."""

from __future__ import annotations

import json
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


@pytest.mark.parametrize("store", [JsonStorage(), CsvStorage()])
def test_policy_append_to_missing_file_is_read_modify_write(
    tmp_path: Path, store: object
) -> None:
    suffix = ".json" if isinstance(store, JsonStorage) else ".csv"
    path = tmp_path / f"append{suffix}"
    policy = SafeIoPolicy.for_root(tmp_path)

    async def exercise() -> None:
        await store.write(  # type: ignore[attr-defined]
            binding="append",
            location=str(path),
            data=[{"id": 1}],
            contract_type=None,
            context={"safe_io": policy, "write_mode": "append"},
        )
        await store.write(  # type: ignore[attr-defined]
            binding="append",
            location=str(path),
            data=[{"id": 2}],
            contract_type=None,
            context={"safe_io": policy, "write_mode": "append"},
        )
        rows = await store.read(  # type: ignore[attr-defined]
            binding="append",
            location=str(path),
            contract_type=None,
            context={"safe_io": policy},
        )
        assert len(rows) == 2

    anyio.run(exercise)


def test_policy_csv_preserves_embedded_newlines(tmp_path: Path) -> None:
    path = tmp_path / "multiline.csv"
    path.write_bytes(b'id,label\r\n1,"a\r\nb"\r\n')
    policy = SafeIoPolicy.for_root(tmp_path)

    async def exercise() -> None:
        rows = await CsvStorage().read(
            binding="input",
            location=str(path),
            contract_type=None,
            context={"safe_io": policy},
        )
        assert rows == [{"id": "1", "label": "a\r\nb"}]
        await CsvStorage().write(
            binding="input",
            location=str(path),
            data=[{"id": 2, "label": "c"}],
            contract_type=None,
            context={"safe_io": policy, "write_mode": "append"},
        )

    anyio.run(exercise)
    assert b'1,"a\r\nb"\r\n' in path.read_bytes()


def test_csv_append_without_policy_preserves_a_concurrent_append(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "concurrent.csv"
    path.write_bytes(b"id,label\r\n1,a\r\n")
    store = CsvStorage()
    original_append_text = store._append_text

    def competing_append(
        existing: str,
        rows: list[dict[str, object]],
        contract_type: type[object] | None,
    ) -> str:
        updated = original_append_text(existing, rows, contract_type)
        with path.open("a", newline="", encoding="utf-8") as handle:
            handle.write("3,c\r\n")
        return updated

    monkeypatch.setattr(store, "_append_text", competing_append)

    async def exercise() -> None:
        await store.write(
            binding="rows",
            location=str(path),
            data=[{"id": 2, "label": "b"}],
            contract_type=None,
            context={"write_mode": "append"},
        )

    anyio.run(exercise)
    assert path.read_bytes() == b"id,label\r\n1,a\r\n3,c\r\n2,b\r\n"


def test_json_append_preserves_existing_scalar_records(tmp_path: Path) -> None:
    path = tmp_path / "values.json"
    path.write_text('[1, "old", null]\n', encoding="utf-8")

    async def exercise() -> None:
        await JsonStorage().write(
            binding="values",
            location=str(path),
            data=[{"id": 2}],
            contract_type=None,
            context={"write_mode": "append"},
        )

    anyio.run(exercise)
    assert json.loads(path.read_text(encoding="utf-8")) == [
        1,
        "old",
        None,
        {"id": 2},
    ]
