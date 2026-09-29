"""Regression coverage for bounded storage-provider materialization (#162)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from etlantic.storage import protocol as storage_protocol
from etlantic.storage.protocol import as_records, records_to_dicts


def test_none_max_rows_rejects_provider_before_conversion() -> None:
    class InfiniteProvider:
        def __init__(self) -> None:
            self.converted = False

        def to_dicts(self):
            self.converted = True
            index = 0
            while True:
                yield {"id": index}
                index += 1

    provider = InfiniteProvider()
    with pytest.raises(ValueError, match="finite max_rows"):
        as_records(provider, None, max_rows=None)
    assert provider.converted is False


def test_none_max_rows_rejects_generic_iterable_before_iteration() -> None:
    consumed = 0

    def rows():
        nonlocal consumed
        while True:
            consumed += 1
            yield {"id": consumed}

    with pytest.raises(ValueError, match="finite max_rows"):
        records_to_dicts(rows(), max_rows=None)
    assert consumed == 0


def test_self_returning_head_is_not_treated_as_bounded() -> None:
    class SelfHeadProvider:
        def head(self, count: int):
            return self

        def to_dicts(self):
            raise AssertionError("unbounded conversion was called")

    with pytest.raises(ValueError, match="unbounded source"):
        as_records(SelfHeadProvider(), None, max_rows=2)


def test_provider_without_head_is_rejected_before_conversion() -> None:
    class UnboundedProvider:
        def to_dicts(self):
            raise AssertionError("conversion was called")

    with pytest.raises(ValueError, match="bounded head view"):
        as_records(UnboundedProvider(), None, max_rows=2)


def test_marked_bounded_view_consumes_only_row_limit_plus_sentinel() -> None:
    consumed = 0

    class View:
        __etlantic_bounded_view__ = True

        def to_dicts(self):
            nonlocal consumed
            for index in range(1000):
                consumed += 1
                yield {"id": index}

    class Provider:
        def head(self, count: int):
            assert count == 3
            return View()

        def to_dicts(self):
            raise AssertionError("the unbounded provider was converted")

    with pytest.raises(ValueError, match="max_rows=2"):
        records_to_dicts(Provider(), max_rows=2)
    assert consumed == 3


def test_unmarked_custom_head_view_is_rejected() -> None:
    class View:
        def to_dicts(self):
            raise AssertionError("conversion was called")

    class Provider:
        def head(self, count: int):
            return View()

        def to_dicts(self):
            raise AssertionError("the unbounded provider was converted")

    with pytest.raises(ValueError, match="did not prove a bounded view"):
        as_records(Provider(), None, max_rows=2)


@pytest.mark.parametrize("error_type", [RuntimeError, ValueError])
def test_provider_conversion_failure_is_stable_and_does_not_leak_error(
    error_type: type[Exception],
) -> None:
    class View:
        __etlantic_bounded_view__ = True

        def to_dicts(self):
            raise error_type("provider secret and source rows")

    class Provider:
        def head(self, count: int):
            return View()

        def to_dicts(self):
            raise AssertionError("the unbounded provider was converted")

    with pytest.raises(ValueError, match="provider conversion failed") as caught:
        as_records(Provider(), None, max_rows=2)
    assert "provider secret" not in str(caught.value)


def test_eager_provider_conversion_checks_declared_size_before_conversion() -> None:
    class View:
        __etlantic_bounded_view__ = True
        estimated_size = 4096

        def __init__(self) -> None:
            self.converted = False

        def to_dicts(self):
            self.converted = True
            return [{"id": 1}]

    view = View()

    class Provider:
        def head(self, count: int):
            assert count == 3
            return view

    with pytest.raises(ValueError, match="max_bytes"):
        as_records(Provider(), None, max_rows=2, max_bytes=64)
    assert view.converted is False


def test_streaming_provider_rows_stop_at_byte_limit() -> None:
    consumed = 0

    class View:
        __etlantic_bounded_view__ = True

        def iter_rows(self, *, named: bool):
            assert named is True
            nonlocal consumed
            for index in range(100):
                consumed += 1
                yield {"id": index, "value": "x" * 128}

    class Provider:
        def head(self, count: int):
            assert count == 3
            return View()

    with pytest.raises(ValueError, match="max_bytes"):
        as_records(Provider(), None, max_rows=2, max_bytes=64)
    assert consumed == 1


def test_streaming_provider_rows_obey_cooperative_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = 0.0

    class Clock:
        @staticmethod
        def monotonic() -> float:
            return now

    monkeypatch.setattr(storage_protocol, "time", Clock)

    class View:
        __etlantic_bounded_view__ = True

        def iter_rows(self, *, named: bool):
            assert named is True
            nonlocal now
            now = 0.002
            yield {"id": 1}

    class Provider:
        def head(self, count: int):
            assert count == 3
            return View()

    with pytest.raises(ValueError, match="timeout_seconds"):
        as_records(Provider(), None, max_rows=2, timeout_seconds=0.001)


@pytest.mark.parametrize("column_labels", [(1, "1"), ("id", "id")])
@pytest.mark.parametrize("adapter", ["pandas", "iter_rows", "fetchmany"])
def test_provider_adapters_reject_invalid_column_names(
    column_labels: tuple[object, ...], adapter: str
) -> None:
    converted: list[str] = []

    class PandasView:
        __module__ = "pandas"
        __etlantic_bounded_view__ = True

        def __init__(self) -> None:
            self.columns = column_labels

        def itertuples(self, *, index: bool, name: object) -> Iterator[tuple[str, str]]:
            converted.append("pandas")
            return iter((("left", "right"),))

    class IterRowsView:
        __etlantic_bounded_view__ = True

        def __init__(self) -> None:
            self.columns = column_labels

        def iter_rows(self) -> Iterator[tuple[str, str]]:
            return iter((("left", "right"),))

    class FetchmanyView:
        __etlantic_bounded_view__ = True

        def __init__(self) -> None:
            self.columns = column_labels

        def fetchmany(self, size: int) -> list[tuple[str, str]]:
            converted.append("fetchmany")
            return [("left", "right")] if len(converted) == 1 else []

    view_type: type[Any]
    if adapter == "pandas":
        view_type = PandasView
    elif adapter == "iter_rows":
        view_type = IterRowsView
    else:
        view_type = FetchmanyView

    class Provider:
        def head(self, count: int) -> Any:
            assert count == 3
            return view_type()

    with pytest.raises(ValueError, match="provider column names"):
        as_records(Provider(), None, max_rows=2)

    assert converted == []


def test_wide_pandas_columns_are_bounded_before_tuple_conversion() -> None:
    conversions = 0
    labels = tuple(f"column_{index}" for index in range(10_000))

    class PandasView:
        __module__ = "pandas.core.frame"

        def __init__(self) -> None:
            self.columns = labels

        def __len__(self) -> int:
            return 1

        def head(self, count: int) -> PandasView:
            assert count == 3
            return PandasView()

        def itertuples(self, *, index: bool, name: Any) -> Iterator[tuple[Any, ...]]:
            nonlocal conversions
            conversions += 1
            return iter([tuple(range(len(labels)))])

    class Provider:
        def head(self, count: int) -> PandasView:
            assert count == 3
            return PandasView()

    with pytest.raises(ValueError, match=r"provider column names.*max_bytes"):
        as_records(Provider(), None, max_rows=2, max_bytes=64)

    assert conversions == 0
