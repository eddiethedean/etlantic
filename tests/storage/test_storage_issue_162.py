"""Regression coverage for bounded storage-provider materialization (#162)."""

from __future__ import annotations

import pytest

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


def test_provider_conversion_failure_is_stable_and_does_not_leak_error() -> None:
    class View:
        __etlantic_bounded_view__ = True

        def to_dicts(self):
            raise RuntimeError("provider secret and source rows")

    class Provider:
        def head(self, count: int):
            return View()

        def to_dicts(self):
            raise AssertionError("the unbounded provider was converted")

    with pytest.raises(ValueError, match="provider conversion failed") as caught:
        as_records(Provider(), None, max_rows=2)
    assert "provider secret" not in str(caught.value)
