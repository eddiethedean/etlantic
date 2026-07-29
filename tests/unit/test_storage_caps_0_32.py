"""Unit tests for 0.32 storage.delta.* capability vocabulary and catalog policy."""

from __future__ import annotations

import pytest

from etlantic.bindings import AssetBindingRef
from etlantic.capabilities import PluginCapabilities, validate_capability_claims
from etlantic.catalog_policy import CatalogMutationKind, CatalogMutationPolicy
from etlantic.exceptions import PipelineValidationError
from etlantic.planning.capabilities import assert_storage_delta_capabilities
from etlantic.spark.protocol import (
    SparkDataFrameHandle,
    logical_identities_for_region,
)
from etlantic.storage import (
    STORAGE_DELTA_CAPABILITY_EXTRAS,
    DeltaStorageOp,
    storage_capability_for_delta_op,
)


def test_storage_delta_extras_constant() -> None:
    assert "storage.delta.merge" in STORAGE_DELTA_CAPABILITY_EXTRAS
    assert "storage.delta.optimize" in STORAGE_DELTA_CAPABILITY_EXTRAS
    assert storage_capability_for_delta_op(DeltaStorageOp.VACUUM) == (
        "storage.delta.vacuum"
    )


def test_storage_extra_implies_spark_delta() -> None:
    broken = PluginCapabilities(
        engine="broken",
        spark=False,
        spark_delta=False,
        extras=frozenset({"storage.delta.optimize"}),
    )
    findings = validate_capability_claims(broken)
    assert findings
    assert any("storage.delta.optimize" in item for item in findings)

    ok = PluginCapabilities(
        engine="ok",
        spark=True,
        spark_delta=True,
        extras=frozenset({"storage.delta.optimize", "storage.delta.vacuum"}),
    )
    assert validate_capability_claims(ok) == []


def test_assert_storage_delta_fail_closed() -> None:
    caps = PluginCapabilities(engine="pyspark", spark=True, spark_delta=True)
    with pytest.raises(PipelineValidationError) as exc:
        assert_storage_delta_capabilities(
            operations=["optimize", "vacuum"],
            available=caps,
            engine="pyspark",
        )
    codes = {d.code for d in exc.value.report.diagnostics}
    assert "PMPLAN441" in codes

    merge_ok = PluginCapabilities(
        engine="pyspark", spark=True, spark_delta=True, spark_merge=True
    )
    assert_storage_delta_capabilities(
        operations=["merge"],
        available=merge_ok,
        engine="pyspark",
    )

    fine = PluginCapabilities(
        engine="pyspark",
        spark=True,
        spark_delta=True,
        extras=frozenset(
            {
                "storage.delta.optimize",
                "storage.delta.vacuum",
                "storage.delta.history",
            }
        ),
    )
    assert_storage_delta_capabilities(
        operations=["optimize", "vacuum", "history"],
        available=fine,
        engine="pyspark",
    )


def test_assert_storage_missing_caps() -> None:
    with pytest.raises(PipelineValidationError) as exc:
        assert_storage_delta_capabilities(
            operations=["merge"],
            available=None,
            engine="pyspark",
        )
    assert any(d.code == "PMPLAN440" for d in exc.value.report.diagnostics)


def test_catalog_mutation_production_fail_closed() -> None:
    policy = CatalogMutationPolicy(allow_mutations=False)
    diags = policy.authorize(
        CatalogMutationKind.CREATE_TABLE,
        namespace="bronze",
        profile_name="production",
        security_mode="production",
    )
    assert diags and diags[0].code == "PMCAT100"

    allowed = CatalogMutationPolicy(
        allow_mutations=True,
        allowed_kinds=frozenset({CatalogMutationKind.CREATE_TABLE.value}),
        allowed_namespaces=frozenset({"bronze"}),
    )
    assert (
        allowed.authorize(
            CatalogMutationKind.CREATE_TABLE,
            namespace="bronze",
            profile_name="production",
            security_mode="production",
        )
        == []
    )


def test_asset_binding_ref_jdbc() -> None:
    ref = AssetBindingRef.from_descriptor(
        "orders",
        "jdbc://warehouse/orders",
        catalog="main",
        namespace="sales",
        table="orders",
        secret_refs={"password": "secrets/db"},
        cross_schema=True,
    )
    assert ref.provider == "jdbc"
    assert ref.format == "jdbc"
    assert ref.cross_schema is True
    assert "password" not in str(ref.to_dict().get("location"))
    assert ref.secret_refs["password"] == "secrets/db"
    roundtrip = AssetBindingRef.from_dict(ref.to_dict())
    assert roundtrip.name == "orders"


def test_logical_identities_and_handle() -> None:
    ids = logical_identities_for_region(("clean", "kpis"), region_id="region-1")
    assert ids["clean"] == "region-1:clean"
    handle = SparkDataFrameHandle(
        identity="phys-1",
        step_name="clean",
        region_id="region-1",
        metadata={"logical_step_id": "region-1:clean"},
    )
    assert handle.logical_step_id == "region-1:clean"


def test_catalog_default_deny_and_production_flag() -> None:
    # Non-production default deny when allow_mutations is False.
    denied = CatalogMutationPolicy(allow_mutations=False)
    assert (
        denied.allows(CatalogMutationKind.CREATE_TABLE, profile_name="development")
        is False
    )

    # Explicit allow works in non-production.
    allowed = CatalogMutationPolicy(allow_mutations=True)
    assert (
        allowed.allows(CatalogMutationKind.CREATE_TABLE, profile_name="development")
        is True
    )

    # production_fail_closed=False falls back to allow_mutations (still deny here).
    openish = CatalogMutationPolicy(
        allow_mutations=False,
        production_fail_closed=False,
    )
    assert (
        openish.allows(
            CatalogMutationKind.CREATE_TABLE,
            profile_name="production",
            security_mode="production",
        )
        is False
    )


def test_collect_and_plan_storage_delta_ops() -> None:
    from etlantic.planning.capabilities import collect_required_delta_operations
    from etlantic.profile import Profile

    profile = Profile(
        name="spark",
        spark_engine="pyspark",
        required_spark_capabilities=("storage.delta.optimize", "write.merge"),
    )
    ops = collect_required_delta_operations(profile=profile)
    assert "optimize" in ops
    assert "merge" in ops
