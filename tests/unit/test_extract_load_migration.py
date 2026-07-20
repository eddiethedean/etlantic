"""Removed-surface coverage for Extract/Load/asset after 0.16 cleanup."""

from __future__ import annotations

import pytest

from etlantic import Extract, Load, Pipeline
from etlantic.profile import Profile
from etlantic.runtime.request import RunRequest
from tests.conftest import Customer, RawCustomer
from tests.fixtures.extract_load_golden_pipeline import ExtractLoadGoldenPipeline


def test_source_and_sink_not_exported() -> None:
    import etlantic

    assert not hasattr(etlantic, "Source")
    assert not hasattr(etlantic, "Sink")
    with pytest.raises(AttributeError, match="Extract"):
        _ = etlantic.Source
    with pytest.raises(AttributeError, match="Load"):
        _ = etlantic.Sink
    with pytest.raises(ImportError):
        from etlantic import Source  # noqa: F401
    with pytest.raises(ImportError):
        from etlantic import Sink  # noqa: F401


def test_binding_kwarg_rejected() -> None:
    with pytest.raises(TypeError, match="binding="):
        Extract(binding="raw")
    with pytest.raises(TypeError, match="binding="):
        Load(input=None, binding="out")
    with pytest.raises(TypeError, match="binding="):
        Extract(asset="raw", binding="raw")


def test_extract_asset_required() -> None:
    with pytest.raises(TypeError, match="asset="):
        Extract()
    with pytest.raises(ValueError, match="non-empty"):
        Extract(asset="  ")


def test_binding_property_removed() -> None:
    extract = Extract(asset="raw")
    assert (
        not hasattr(type(extract), "binding") or "binding" not in type(extract).__dict__
    )
    with pytest.raises(AttributeError):
        _ = extract.binding  # type: ignore[attr-defined]


def test_profile_bindings_ctor_rejected() -> None:
    with pytest.raises(TypeError, match="bindings"):
        Profile(name="demo", bindings={"raw": "memory"})


def test_profile_assets_ok() -> None:
    profile = Profile(name="demo", assets={"raw": "memory"})
    assert profile.assets == {"raw": "memory"}
    assert profile.bindings == {"raw": "memory"}
    public = profile.to_dict()
    assert public["assets"] == {"raw": "memory"}
    assert "bindings" not in public
    snap = profile.to_plan_snapshot()
    assert snap["bindings"] == {"raw": "memory"}
    assert "assets" not in snap


def test_profile_from_dict_reads_legacy_bindings() -> None:
    profile = Profile.from_dict(
        {"name": "demo", "security_mode": "development", "bindings": {"raw": "memory"}},
        accept_legacy_bindings=True,
    )
    assert profile.assets == {"raw": "memory"}
    assert "bindings" not in profile.to_dict()


def test_run_request_binding_overrides_rejected() -> None:
    with pytest.raises(TypeError, match="binding_overrides"):
        RunRequest(binding_overrides={"raw": "alt"})


def test_run_request_asset_overrides_ok() -> None:
    request = RunRequest(asset_overrides={"raw": "alt"})
    assert request.asset_overrides == {"raw": "alt"}
    assert "binding_overrides" not in request.to_dict()


def test_member_rebuild_ok() -> None:
    class Tiny(Pipeline):
        raw: Extract[RawCustomer] = Extract(asset="raw")
        out: Load[Customer] = Load(input=raw, asset="out")

    Tiny.build_graph()
    Tiny.validate()


def test_dpcs_round_trip_ok(tmp_path) -> None:
    from etlantic.interchange.bundle import load_bundle, write_contracts

    write_contracts(ExtractLoadGoldenPipeline, tmp_path)
    loaded = load_bundle(tmp_path)
    assert loaded.pipeline is not None
    loaded.pipeline.build_graph()


def test_example_quickstart_import_ok() -> None:
    import importlib
    import sys

    sys.modules.pop("examples.quickstart", None)
    importlib.import_module("examples.quickstart")
