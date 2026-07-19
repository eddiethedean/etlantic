"""Deprecation and conflict coverage for Extract/Load/asset migration."""

from __future__ import annotations

import warnings

import pytest

from etlantic import Extract, Load, Pipeline, Sink, Source
from etlantic.profile import Profile
from etlantic.runtime.request import RunRequest
from tests.conftest import Customer, RawCustomer
from tests.fixtures.extract_load_golden_pipeline import ExtractLoadGoldenPipeline


def _deprecation_messages(caught: list[warnings.WarningMessage]) -> list[str]:
    return [str(item.message) for item in caught]


def test_source_binding_emits_one_warning() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        source = Source[RawCustomer](binding="raw")
    messages = _deprecation_messages(caught)
    assert len(messages) == 1
    assert "Source" in messages[0]
    assert "binding=" in messages[0]
    assert "0.16" in messages[0]
    assert source.asset == "raw"


def test_sink_binding_emits_one_warning() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        sink = Sink[Customer](input=None, binding="out")
    messages = _deprecation_messages(caught)
    assert len(messages) == 1
    assert "Sink" in messages[0]
    assert "binding=" in messages[0]
    assert sink.asset == "out"


def test_extract_binding_warns_only_for_binding() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        extract = Extract[RawCustomer](binding="raw")
    messages = _deprecation_messages(caught)
    assert len(messages) == 1
    assert "binding=" in messages[0]
    assert "Source" not in messages[0]
    assert extract.asset == "raw"


def test_source_asset_warns_only_for_source() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        source = Source[RawCustomer](asset="raw")
    messages = _deprecation_messages(caught)
    assert len(messages) == 1
    assert "Source" in messages[0]
    assert "binding=" not in messages[0]
    assert source.asset == "raw"


def test_extract_asset_emits_no_warning() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        Extract[RawCustomer](asset="raw")
        Load[Customer](input=None, asset="out")
    assert _deprecation_messages(caught) == []


def test_reject_simultaneous_asset_and_binding() -> None:
    with pytest.raises(TypeError, match="not both"):
        Extract(asset="raw", binding="raw")
    with pytest.raises(TypeError, match="not both"):
        Load(input=None, asset="out", binding="out")


def test_reject_empty_asset_identifier() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        Extract(asset="  ")


def test_isinstance_source_sink_compat() -> None:
    extract = Extract(asset="raw")
    load = Load(input=None, asset="out")
    source = Source(asset="raw", _compat_warn=False)
    sink = Sink(input=None, asset="out", _compat_warn=False)
    assert isinstance(source, Extract)
    assert isinstance(sink, Load)
    assert isinstance(extract, Extract)
    assert isinstance(load, Load)


def test_binding_property_warns() -> None:
    extract = Extract(asset="raw")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        assert extract.binding == "raw"
    assert len(_deprecation_messages(caught)) == 1


def test_member_rebuild_emits_no_warning() -> None:
    class Tiny(Pipeline):
        raw: Extract[RawCustomer] = Extract(asset="raw")
        out: Load[Customer] = Load(input=raw, asset="out")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        Tiny.build_graph()
        Tiny.validate()
    assert _deprecation_messages(caught) == []


def test_dpcs_round_trip_emits_no_warning(tmp_path) -> None:
    from etlantic.interchange.bundle import load_bundle, write_contracts

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        write_contracts(ExtractLoadGoldenPipeline, tmp_path)
        loaded = load_bundle(tmp_path)
        assert loaded.pipeline is not None
        loaded.pipeline.build_graph()
    messages = [
        message
        for message in _deprecation_messages(caught)
        if "0.15" in message
        or "Source" in message
        or "Sink" in message
        or "binding=" in message
        or "Profile.bindings" in message
    ]
    assert messages == []


def test_profile_bindings_warns_once() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        profile = Profile(name="demo", bindings={"raw": "memory"})
    messages = _deprecation_messages(caught)
    assert len(messages) == 1
    assert "Profile.bindings" in messages[0]
    assert profile.assets == {"raw": "memory"}


def test_profile_assets_no_warning() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        profile = Profile(name="demo", assets={"raw": "memory"})
    assert _deprecation_messages(caught) == []
    assert profile.bindings == {"raw": "memory"}


def test_profile_rejects_disagreeing_maps() -> None:
    with pytest.raises(ValueError, match="disagree"):
        Profile(name="demo", assets={"a": "memory"}, bindings={"a": "csv"})


def test_run_request_binding_overrides_warns() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        request = RunRequest(binding_overrides={"raw": "alt"})
    messages = _deprecation_messages(caught)
    assert len(messages) == 1
    assert "binding_overrides" in messages[0]
    assert request.asset_overrides == {"raw": "alt"}


def test_run_request_asset_overrides_no_warning() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        request = RunRequest(asset_overrides={"raw": "alt"})
    assert _deprecation_messages(caught) == []
    assert request.binding_overrides == {"raw": "alt"}


def test_example_quickstart_import_is_quiet() -> None:
    import importlib
    import sys

    sys.modules.pop("examples.quickstart", None)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        importlib.import_module("examples.quickstart")
    messages = [
        message
        for message in _deprecation_messages(caught)
        if any(
            token in message
            for token in ("Source", "Sink", "binding=", "Profile.bindings", "0.16")
        )
    ]
    assert messages == []
