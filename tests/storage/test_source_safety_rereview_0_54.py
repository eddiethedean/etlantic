# pyright: reportAttributeAccessIssue=false, reportMissingImports=false, reportMissingParameterType=false, reportMissingTypeStubs=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownVariableType=false
"""Real native regressions for source re-review findings 4, 5, 10 and 11."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

pl = pytest.importorskip("polars")
pa = pytest.importorskip("pyarrow")
pq = pytest.importorskip("pyarrow.parquet")

from etlantic.io_policy import SafeIoPolicy  # noqa: E402
from etlantic_polars import PolarsParquetStorage  # noqa: E402
from etlantic_polars.fusion import inspect_fusion_query  # noqa: E402
from etlantic_polars.parquet_storage import _sanitize_footer  # noqa: E402

pytestmark = pytest.mark.polars


@pytest.mark.parametrize(
    "failure", [pl.exceptions.PanicException, asyncio.CancelledError]
)
def test_explicit_read_sanitizes_native_panic_preserves_control_flow(
    tmp_path, monkeypatch, failure
):
    pl.DataFrame({"key": [1]}).write_parquet(tmp_path / "raw.parquet")

    def collect(*args, **kwargs):
        raise failure("secret-native-payload-and-path")

    monkeypatch.setattr(pl.LazyFrame, "collect", collect)
    if failure is asyncio.CancelledError:
        with pytest.raises(asyncio.CancelledError):
            read(tmp_path)
    else:
        with pytest.raises(
            ValueError, match="Bounded Parquet read/contract validation failed"
        ) as caught:
            read(tmp_path)
        assert "secret-native" not in str(caught.value)
        assert caught.value.__suppress_context__


def context(root):
    return {"safe_io": SafeIoPolicy.for_root(root)}


def read(root):
    return asyncio.run(
        PolarsParquetStorage().read(
            binding="raw",
            location="raw.parquet",
            contract_type=None,
            context=context(root),
        )
    )


def test_native_snapshot_survives_parent_rename_and_replacement(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    original = pl.DataFrame({"key": [1], "enabled": [True]})
    original.write_parquet(root / "raw.parquet")
    storage = PolarsParquetStorage()
    with storage.open_scan(location="raw.parquet", context=context(root)) as scan:
        assert "in-mem bytes" in scan.explain()
        moved = tmp_path / "moved"
        root.rename(moved)
        root.mkdir()
        replacement = pl.DataFrame({"key": [99], "enabled": [False]})
        replacement.write_parquet(root / "raw.parquet")
        replacement.write_parquet(moved / "raw.parquet")
        assert scan.collect().equals(original)
    assert pl.read_parquet(root / "raw.parquet").equals(replacement)
    assert pl.read_parquet(moved / "raw.parquet").equals(replacement)
    assert not storage.pending_snapshot_cleanups()
    assert not list(tmp_path.rglob("etlantic-parquet-*"))


@pytest.mark.parametrize("storage_type", [pa.int64(), pa.string()])
def test_registered_extension_callback_never_runs(tmp_path, storage_type):
    callbacks = []
    name = "etlantic.rereview.callback"

    class Callback(pa.ExtensionType):
        def __init__(self):
            super().__init__(storage_type, name)

        def __arrow_ext_serialize__(self):
            return b"attacker-controlled-extension-payload"

        @classmethod
        def __arrow_ext_deserialize__(cls, dtype, serialized):
            callbacks.append((dtype, serialized))
            raise AssertionError("untrusted extension callback executed")

    extension = Callback()
    pa.register_extension_type(extension)
    try:
        values = [1, None] if storage_type == pa.int64() else ["unsafe", None]
        array = pa.ExtensionArray.from_storage(
            extension, pa.array(values, storage_type)
        )
        pq.write_table(
            pa.table({"key": array, "enabled": [True, None]}), tmp_path / "raw.parquet"
        )
        if storage_type == pa.int64():
            assert read(tmp_path).to_dicts() == [
                {"key": 1, "enabled": True},
                {"key": None, "enabled": None},
            ]
        else:
            with pytest.raises(ValueError, match="primitive"):
                read(tmp_path)
        assert callbacks == []
    finally:
        pa.unregister_extension_type(name)


def test_scrub_precedes_arrow_constructor_and_uses_arrow14_20_surface(
    tmp_path, monkeypatch
):
    frame = pl.DataFrame(
        {"key": [1, None], "enabled": [True, None]},
        schema={"key": pl.Int64, "enabled": pl.Boolean},
    )
    frame.write_parquet(tmp_path / "raw.parquet")
    native = pq.ParquetFile
    seen = []

    def constructor(source, **kwargs):
        assert "arrow_extensions_enabled" not in kwargs
        parquet = native(source, **kwargs)
        assert b"ARROW:schema" not in (parquet.metadata.metadata or {})
        seen.append(True)
        return parquet

    monkeypatch.setattr(pq, "ParquetFile", constructor)
    assert read(tmp_path).equals(frame)
    assert seen == [True]


@pytest.mark.parametrize(
    "column",
    [
        'a"b',
        "a\\b",
        "a\nb",
        "a\tb",
        "a\rb",
        "é space",
        "key\nFILTER item",
        "key\nPROJECT 1/3 COLUMNS",
        "key\nParquet SCAN [name]",
    ],
)
def test_raw_column_names_have_actual_native_scan_proof(tmp_path, column):
    frame = pl.DataFrame(
        {
            column: [1, 2],
            "enabled": [True, False],
            "unused": [9, 9],
            "__etlantic_predicate__": [2, 1],
        }
    )
    frame.write_parquet(tmp_path / "raw.parquet")
    descriptor = SimpleNamespace(
        members=(
            SimpleNamespace(
                definition={
                    "actions": [
                        {
                            "kind": {
                                "parameters": {
                                    "predicate": {
                                        "left": {"target": column},
                                        "right": {"target": "key"},
                                    },
                                }
                            }
                        }
                    ]
                }
            ),
            SimpleNamespace(
                definition={
                    "actions": [
                        {
                            "kind": {
                                "parameters": {
                                    "fields": [column, "enabled"],
                                }
                            }
                        }
                    ]
                }
            ),
        ),
        parameters={"key": 1},
    )
    with PolarsParquetStorage().open_scan(
        location="raw.parquet", context=context(tmp_path)
    ) as scan:
        query = scan.filter(pl.col(column) == 1).select(column, "enabled")
        proof = inspect_fusion_query(query, descriptor)
        assert proof["scan_predicate"] and proof["scan_projection"]
        assert query.collect().equals(frame.head(1).select(column, "enabled"))
        wrong = scan.filter(pl.col("__etlantic_predicate__") == 1).select(
            column, "enabled"
        )
        assert not inspect_fusion_query(wrong, descriptor)["scan_predicate"]


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"PAR1" + b"\xff" * 8,
        b"PAR1\x36\x80\x00" + (3).to_bytes(4, "little") + b"PAR1",
        b"PAR1\x19\xfc\xff\xff\xff\xff\x7f\x00" + (8).to_bytes(4, "little") + b"PAR1",
    ],
)
def test_malformed_footer_fails_before_native(payload):
    with pytest.raises(ValueError):
        _sanitize_footer(payload, 100)


def test_footer_row_bound_before_any_arrow_reader(tmp_path, monkeypatch):
    frame = pl.DataFrame({"key": [1, 2]})
    frame.write_parquet(tmp_path / "raw.parquet")

    def forbidden(*args, **kwargs):
        pytest.fail("Arrow constructed before pure footer row bound")

    monkeypatch.setattr(pq, "ParquetFile", forbidden)
    with (
        pytest.raises(ValueError, match="row bounds"),
        PolarsParquetStorage(max_rows=1).open_scan(
            location="raw.parquet",
            context=context(tmp_path),
        ),
    ):
        pytest.fail("row overflow acquired native scan")
