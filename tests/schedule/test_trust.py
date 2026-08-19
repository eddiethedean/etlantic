"""Production resource-provider allowlist and memory-store rejection."""

from __future__ import annotations

import pytest

from etlantic.control_plane import (
    MemoryScheduleStore,
    assert_schedule_store_allowed,
    resource_provider_allowed,
)
from etlantic.profile import Profile, production_profile
from etlantic.profile import test_profile as make_test_profile


def test_production_empty_allowlist_selected_fails() -> None:
    profile = production_profile(plugin_allowlist={"etlantic-polars": "==0.48.0"})
    allowed, diag = resource_provider_allowed(profile, "etlantic-k8s", selected=True)
    assert not allowed
    assert diag is not None
    assert getattr(diag, "code", "") == "PMRES140"


def test_production_empty_allowlist_not_selected_ok() -> None:
    profile = production_profile(plugin_allowlist={"etlantic-polars": "==0.48.0"})
    allowed, diag = resource_provider_allowed(profile, "etlantic-k8s", selected=False)
    assert allowed
    assert diag is None


def test_production_pin_allows_matching_package() -> None:
    profile = Profile(
        name="production",
        security_mode="production",
        plugin_allowlist={"etlantic-k8s": "==0.48.0"},
        resource_provider_allowlist={"etlantic-k8s": "==0.48.0"},
    )
    allowed, diag = resource_provider_allowed(
        profile, "etlantic-k8s", version="0.48.0", selected=True
    )
    assert allowed
    assert diag is None


def test_production_rejects_memory_schedule_store() -> None:
    profile = production_profile(plugin_allowlist={"etlantic-polars": "==0.48.0"})
    with pytest.raises(ValueError, match="PMSVC100"):
        assert_schedule_store_allowed(profile, MemoryScheduleStore())


def test_non_production_allows_memory_store() -> None:
    assert_schedule_store_allowed(make_test_profile(), MemoryScheduleStore())


def test_validate_schedule_runtime_rejects_production_memory() -> None:
    from etlantic.control_plane.schedule_trust import validate_schedule_runtime

    profile = production_profile(plugin_allowlist={"etlantic-polars": "==0.48.0"})
    with pytest.raises(ValueError, match="PMSVC100"):
        validate_schedule_runtime(profile, MemoryScheduleStore())
