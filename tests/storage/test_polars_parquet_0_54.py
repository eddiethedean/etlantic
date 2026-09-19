"""Actual bounded Parquet source behavior, independent of adaptive authority."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

pytest.importorskip("polars")
pytest.importorskip("pyarrow")

import polars as pl

from etlantic import Data
from etlantic.interchange.security import UnsafeLoadError
from etlantic.io_policy import SafeIoPolicy
from etlantic.storage.protocol import StorageBinding
from etlantic_polars import PolarsParquetStorage, create_parquet_storage

pytestmark = pytest.mark.polars


def _context(root: Path) -> dict:
    return {"safe_io": SafeIoPolicy.for_root(root)}


def _read(storage: PolarsParquetStorage, root: Path, contract=None):
    return asyncio.run(
        storage.read(
            binding="raw",
            location="raw.parquet",
            contract_type=contract,
            context=_context(root),
        )
    )


def test_public_storage_protocol_and_static_configuration():
    storage = create_parquet_storage()
    assert isinstance(storage, StorageBinding)
    assert create_parquet_storage(storage.configuration()) == storage


@pytest.mark.parametrize("value", [False, True, 0, -1, 1.0, "1", None, 268435457])
def test_invalid_byte_configuration(value):
    with pytest.raises(ValueError, match="configuration"):
        PolarsParquetStorage(max_bytes=value)


@pytest.mark.parametrize("value", [False, True, 0, -1, 1.0, "1", None, 1000001])
def test_invalid_row_configuration(value):
    with pytest.raises(ValueError, match="configuration"):
        PolarsParquetStorage(max_rows=value)


@pytest.mark.parametrize(
    "configuration",
    [
        {},
        {"schema": "unknown", "max_bytes": 1, "max_rows": 1},
        {
            "schema": "etlantic.polars_parquet_source/1",
            "max_bytes": 1,
            "max_rows": 1,
            "secret": "canary",
        },
    ],
)
def test_closed_configuration(configuration):
    with pytest.raises(ValueError, match="configuration"):
        create_parquet_storage(configuration)


@pytest.mark.parametrize(
    "location",
    [
        None,
        "",
        "../raw.parquet",
        "/raw.parquet",
        "s3://raw.parquet",
        "raw*.parquet",
        "raw?.parquet",
        "raw[0].parquet",
        "raw.csv",
        "~user/raw.parquet",
        "a\\raw.parquet",
        "raw\x00.parquet",
    ],
)
def test_bad_locations_reject_before_policy_or_io(location):
    with (
        pytest.raises(ValueError, match="relative file"),
        create_parquet_storage().open_scan(location=location, context={}),
    ):
        pytest.fail("invalid location acquired a scan")


def test_explicit_read_nullable_and_empty(tmp_path):
    frame = pl.DataFrame(
        {"key": [1, None], "enabled": [True, None]},
        schema={"key": pl.Int64, "enabled": pl.Boolean},
    )
    frame.write_parquet(tmp_path / "raw.parquet")
    assert _read(create_parquet_storage(), tmp_path).equals(frame)
    frame.clear().write_parquet(tmp_path / "raw.parquet")
    assert _read(create_parquet_storage(), tmp_path).equals(frame.clear())
    assert not list(tmp_path.glob("etlantic-parquet-*"))


def test_snapshot_is_owned_and_isolates_source_mutation(tmp_path):
    pl.DataFrame({"key": [1]}).write_parquet(tmp_path / "raw.parquet")
    storage = create_parquet_storage()
    with storage.open_scan(location="raw.parquet", context=_context(tmp_path)) as scan:
        assert "in-mem bytes" in scan.explain()
        assert not list(tmp_path.glob("etlantic-parquet-*"))
        pl.DataFrame({"key": [2]}).write_parquet(tmp_path / "raw.parquet")
        assert scan.collect()["key"].to_list() == [1]
    assert not list(tmp_path.glob("etlantic-parquet-*"))
    assert not storage.pending_snapshot_cleanups()


def test_snapshot_cleanup_on_caller_failure(tmp_path):
    pl.DataFrame({"key": [1]}).write_parquet(tmp_path / "raw.parquet")
    storage = create_parquet_storage()
    with (
        pytest.raises(RuntimeError, match="caller"),
        storage.open_scan(location="raw.parquet", context=_context(tmp_path)),
    ):
        raise RuntimeError("caller")
    assert not list(tmp_path.glob("etlantic-parquet-*"))
    assert not storage.pending_snapshot_cleanups()


def test_all_columns_checked_even_when_unused(tmp_path):
    pl.DataFrame({"key": [1], "discarded": ["unsafe"]}).write_parquet(
        tmp_path / "raw.parquet"
    )
    with pytest.raises(ValueError, match="primitive"):
        _read(create_parquet_storage(), tmp_path)
    assert not list(tmp_path.glob("etlantic-parquet-*"))


def test_row_bound_exact_and_first_excess(tmp_path):
    pl.DataFrame({"key": [1, 2]}).write_parquet(tmp_path / "raw.parquet")
    assert _read(PolarsParquetStorage(max_rows=2), tmp_path).height == 2
    with pytest.raises(ValueError, match="row bounds"):
        _read(PolarsParquetStorage(max_rows=1), tmp_path)


def test_byte_bound_rejects_before_decode(tmp_path):
    pl.DataFrame({"key": [1]}).write_parquet(tmp_path / "raw.parquet")
    with pytest.raises(ValueError, match="bounded regular file"):
        _read(PolarsParquetStorage(max_bytes=1), tmp_path)
    assert not list(tmp_path.glob("etlantic-parquet-*"))


def test_uncompressed_budget(tmp_path):
    pl.DataFrame({"key": list(range(20_000))}).write_parquet(
        tmp_path / "raw.parquet", compression="zstd"
    )
    size = (tmp_path / "raw.parquet").stat().st_size
    with pytest.raises(ValueError, match="decoded byte budget"):
        _read(PolarsParquetStorage(max_bytes=size + 1), tmp_path)
    assert not list(tmp_path.glob("etlantic-parquet-*"))


def test_symlink_escape(tmp_path):
    approved = tmp_path / "approved"
    approved.mkdir()
    pl.DataFrame({"key": [1]}).write_parquet(tmp_path / "outside.parquet")
    (approved / "raw.parquet").symlink_to(tmp_path / "outside.parquet")
    with pytest.raises(UnsafeLoadError):
        _read(create_parquet_storage(), approved)
    assert not list(approved.glob("etlantic-parquet-*"))


def test_missing_policy(tmp_path):
    with (
        pytest.raises(ValueError, match="SafeIoPolicy"),
        create_parquet_storage().open_scan(location="raw.parquet", context={}),
    ):
        pytest.fail("missing policy admitted")


def test_readonly_never_resolves_destination(tmp_path):
    with pytest.raises(ValueError, match="read-only"):
        asyncio.run(
            create_parquet_storage().write(
                binding="out",
                location="../../canary",
                data=object(),
                contract_type=None,
                context={},
            )
        )
    assert not list(tmp_path.iterdir())


def test_ordinary_read_enforces_row_contract(tmp_path):
    class Positive(Data):
        key: int

    pl.DataFrame({"other": [1]}).write_parquet(tmp_path / "raw.parquet")
    with pytest.raises(ValueError):
        _read(create_parquet_storage(), tmp_path, Positive)
    assert not list(tmp_path.glob("etlantic-parquet-*"))
