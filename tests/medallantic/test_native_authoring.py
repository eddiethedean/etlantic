"""Native MedallionPipeline / facade conformance tests (no SparkForge install)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("medallantic")

from etlantic.authoring import (
    authoring_graph_fingerprint,
    definition_from_pipeline,
    plan_pipeline_like,
    validate_pipeline_like,
)
from etlantic.reliability import WriteMode
from etlantic.testing import run_facade_conformance_suite
from medallantic import (
    MDL102_CYCLE,
    Bronze,
    Gold,
    LoweringError,
    MedallionBuilder,
    MedallionPipeline,
    Silver,
    SparkForgePipelineSpec,
    adapt_pipeline,
    lower_document,
)
from medallantic.migrate import sparkforge as sparkforge_migrate

pytestmark = pytest.mark.medallantic

FIXTURES = Path(__file__).parent / "fixtures"
PACKAGE_ROOT = (
    Path(__file__).resolve().parents[2] / "packages/medallantic/src/medallantic"
)


def _ecommerce_native() -> MedallionBuilder:
    return (
        MedallionBuilder("ecommerce", schema="demo", engine="local")
        .bronze(
            "orders",
            asset="bronze_orders",
            rules={"id": ["not_null"]},
            description="raw orders",
            tags=("ingest",),
        )
        .silver(
            "clean_orders",
            source="orders",
            asset="silver_orders",
            transform_ref="clean_orders_fn",
            write_mode="overwrite",
            tags=("clean",),
        )
        .gold(
            "order_kpis",
            source="clean_orders",
            asset="gold_order_kpis",
            transform_ref="order_kpis_fn",
            write_mode="merge",
        )
    )


def test_native_ecommerce_matches_ir_topology() -> None:
    data = json.loads((FIXTURES / "ecommerce.json").read_text(encoding="utf-8"))
    ir = adapt_pipeline(SparkForgePipelineSpec.from_dict(data))
    native = _ecommerce_native().lower()
    assert [n.name for n in native.pipeline_cls.inspect().nodes] == data["metadata"][
        "expected_node_order"
    ]
    assert authoring_graph_fingerprint(
        definition_from_pipeline(ir.pipeline_cls)
    ) == authoring_graph_fingerprint(definition_from_pipeline(native.pipeline_cls))
    assert native.layer_by_node["orders"] == "bronze"
    assert native.layer_by_node["clean_orders"] == "silver"
    assert native.layer_by_node["order_kpis"] == "gold"
    by_subject = {w.subject_id: w.mode for w in native.write_intents}
    assert by_subject["silver_orders"] is WriteMode.OVERWRITE
    assert by_subject["gold_order_kpis"] is WriteMode.MERGE


def test_class_authoring_and_definition_round_trip() -> None:
    class Ecommerce(MedallionPipeline):
        __medallion_name__ = "ecommerce"
        __medallion_schema__ = "demo"
        orders = Bronze(asset="bronze_orders", description="raw orders")
        clean_orders = Silver(source="orders", asset="silver_orders")
        order_kpis = Gold(
            source="clean_orders", asset="gold_order_kpis", write_mode="merge"
        )

    defn = Ecommerce.to_definition()
    assert defn.provenance["kind"] == "facade"
    assert defn.provenance["identity"] == "medallantic"
    assert "plugin:medallantic" in defn.extensions
    report = validate_pipeline_like(defn, profile=Ecommerce.lower().profile)
    assert report.valid


def test_facade_conformance_suite() -> None:
    lowered = _ecommerce_native().lower()
    defn = _ecommerce_native().build()
    run_facade_conformance_suite(
        defn,
        profile=lowered.profile,
        facade_package=PACKAGE_ROOT,
    )


def test_migrate_sparkforge_namespace() -> None:
    data = json.loads((FIXTURES / "ecommerce.json").read_text(encoding="utf-8"))
    result = sparkforge_migrate.adapt_pipeline(
        sparkforge_migrate.SparkForgePipelineSpec.from_dict(data)
    )
    assert result.pipeline_cls.inspect().nodes


def test_branch_and_multi_bronze() -> None:
    builder = (
        MedallionBuilder("branchy", schema="demo")
        .bronze("orders", asset="bronze_orders")
        .bronze("customers", asset="bronze_customers")
        .silver("clean_orders", source="orders", asset="silver_orders")
        .silver("clean_customers", source="customers", asset="silver_customers")
        .gold("join_kpis", source="clean_orders", asset="gold_join")
    )
    result = builder.lower()
    names = [n.name for n in result.pipeline_cls.inspect().nodes]
    assert "orders" in names and "customers" in names
    assert result.layer_by_node["orders"] == "bronze"
    assert result.layer_by_node["customers"] == "bronze"


def test_partial_pipeline_bronze_only() -> None:
    result = (
        MedallionBuilder("partial", schema="demo")
        .bronze("orders", asset="bronze_orders")
        .lower()
    )
    names = [n.name for n in result.pipeline_cls.inspect().nodes]
    assert names == ["orders"]
    assert result.write_intents == ()


def test_no_write_skips_sink() -> None:
    result = (
        MedallionBuilder("nowrite", schema="demo")
        .bronze("orders", asset="bronze_orders")
        .silver(
            "clean_orders",
            source="orders",
            asset="silver_orders",
            write_mode="no_write",
        )
        .lower()
    )
    names = [n.name for n in result.pipeline_cls.inspect().nodes]
    assert "clean_orders_out" not in names
    assert result.write_intents[0].mode is WriteMode.NO_WRITE


def test_prior_result_reference() -> None:
    result = (
        MedallionBuilder("prior", schema="demo")
        .bronze("orders", asset="bronze_orders")
        .silver("clean", source="orders.result", asset="silver_orders")
        .lower()
    )
    names = [n.name for n in result.pipeline_cls.inspect().nodes]
    assert "clean" in names


def test_cross_schema_asset_and_plan_extension_survival() -> None:
    lowered = (
        MedallionBuilder("xschema", schema="analytics", engine="local")
        .bronze("orders", asset="other_schema.bronze_orders")
        .silver("clean", source="orders", asset="analytics.silver_orders")
        .lower()
    )
    defn = (
        MedallionBuilder("xschema", schema="analytics", engine="local")
        .bronze("orders", asset="other_schema.bronze_orders")
        .silver("clean", source="orders", asset="analytics.silver_orders")
        .build()
    )
    plan = plan_pipeline_like(defn, profile=lowered.profile)
    assert "plugin:medallantic" in plan.metadata
    assert plan.metadata.get("etlantic.provenance", {}).get("kind") == "facade"
    assert lowered.profile.assets["orders"] == "other_schema.bronze_orders"


def test_cycle_emits_mdl_diagnostic() -> None:
    with pytest.raises(LoweringError) as exc:
        (
            MedallionBuilder("cyclic", schema="demo")
            .silver("a", source="b", asset="a")
            .silver("b", source="a", asset="b")
            .lower()
        )
    codes = {d.code for d in exc.value.report.diagnostics}
    assert MDL102_CYCLE in codes
    assert exc.value.code == MDL102_CYCLE


def test_duplicate_name_error_code_matches_diagnostic() -> None:
    from medallantic import MDL101_DUPLICATE_NAME

    with pytest.raises(LoweringError) as exc:
        (
            MedallionBuilder("dup", schema="demo")
            .bronze("orders", asset="a")
            .bronze("orders", asset="b")
            .lower()
        )
    assert exc.value.code == MDL101_DUPLICATE_NAME
    assert any(d.code == MDL101_DUPLICATE_NAME for d in exc.value.report.diagnostics)


def test_bad_write_mode_error_code_matches_diagnostic() -> None:
    from medallantic import MDL105_BAD_WRITE_MODE

    with pytest.raises(LoweringError) as exc:
        (
            MedallionBuilder("badwrite", schema="demo")
            .bronze("orders", asset="bronze_orders")
            .silver(
                "clean",
                source="orders",
                asset="silver_orders",
                write_mode="not-a-mode",
            )
            .lower()
        )
    assert exc.value.code == MDL105_BAD_WRITE_MODE
    assert any(d.code == MDL105_BAD_WRITE_MODE for d in exc.value.report.diagnostics)


def test_zero_accept_rates_preserved_native_document() -> None:
    from medallantic.schema import MedallionDocument

    doc = MedallionDocument.from_dict(
        {
            "name": "zero",
            "min_bronze_rate": 0.0,
            "min_silver_rate": 0.0,
            "min_gold_rate": 0.0,
            "steps": [
                {
                    "name": "orders",
                    "layer": "bronze",
                    "kind": "bronze_rules",
                    "asset": "b",
                }
            ],
        }
    )
    assert doc.min_bronze_rate == 0.0
    assert doc.min_silver_rate == 0.0
    assert doc.min_gold_rate == 0.0
    lowered = (
        MedallionBuilder(
            "zero",
            schema="demo",
            min_bronze_rate=0.0,
            min_silver_rate=0.0,
            min_gold_rate=0.0,
        )
        .bronze("orders", asset="b")
        .lower()
    )
    rates = lowered.profile.metadata["plugin:medallantic"]["layer_rates"]
    assert rates == {"bronze": 0.0, "silver": 0.0, "gold": 0.0}


def test_unknown_layer_fails_closed() -> None:
    from medallantic import MDL107_UNKNOWN_LAYER
    from medallantic.authoring import from_document
    from medallantic.schema import MedallionDocument, MedallionStep

    with pytest.raises(ValueError, match="Unknown medallion layer"):
        from_document(
            MedallionDocument(
                name="bad",
                steps=(
                    MedallionStep(
                        name="x",
                        layer="platinum",
                        kind="bronze_rules",
                        asset="a",
                    ),
                ),
            )
        )
    with pytest.raises(LoweringError) as exc:
        lower_document(
            MedallionDocument(
                name="bad",
                steps=(
                    MedallionStep(
                        name="x",
                        layer="platinum",
                        kind="bronze_rules",
                        asset="a",
                    ),
                ),
            )
        )
    assert exc.value.code == MDL107_UNKNOWN_LAYER


def test_validation_policy_names_do_not_collide() -> None:
    from etlantic.policy import resolve_validation_policy

    a = (
        MedallionBuilder("pipe_a", schema="default", min_bronze_rate=50.0)
        .bronze("orders", asset="a")
        .lower()
    )
    b = (
        MedallionBuilder("pipe_b", schema="default", min_bronze_rate=99.0)
        .bronze("orders", asset="b")
        .lower()
    )
    assert a.validation_policy.name != b.validation_policy.name
    assert (
        resolve_validation_policy(a.validation_policy.name).metadata[
            "min_accept_rate_ingest"
        ]
        == 50.0
    )
    assert (
        resolve_validation_policy(b.validation_policy.name).metadata[
            "min_accept_rate_ingest"
        ]
        == 99.0
    )


def test_with_metadata_and_step_annotations_survive_definition() -> None:
    lowered = (
        MedallionBuilder("meta", schema="demo")
        .with_metadata(team="analytics", ticket="T-1")
        .bronze(
            "orders",
            asset="bronze_orders",
            description="raw orders",
            tags=("ingest",),
        )
        .lower()
    )
    assert lowered.metadata["document_metadata"] == {
        "team": "analytics",
        "ticket": "T-1",
    }
    assert lowered.metadata["steps"]["orders"]["description"] == "raw orders"
    assert lowered.metadata["steps"]["orders"]["tags"] == ["ingest"]
    ext = lowered.definition.extensions["plugin:medallantic"]
    assert ext["document_metadata"] == {"team": "analytics", "ticket": "T-1"}
    assert ext["steps"]["orders"]["description"] == "raw orders"


def test_declarative_from_dict() -> None:
    doc = {
        "name": "decl",
        "schema": "demo",
        "steps": [
            {"name": "orders", "layer": "bronze", "kind": "bronze_rules", "asset": "b"},
            {
                "name": "clean",
                "layer": "silver",
                "kind": "silver_transform",
                "source": "orders",
                "asset": "s",
                "write_mode": "overwrite",
            },
        ],
    }
    pipe = MedallionPipeline.from_dict(doc)
    defn = pipe.to_definition()
    assert {n.name for n in defn.nodes} >= {"orders", "clean", "clean_out"}
