"""SparkForge adapter parity tests (IR fixtures — no SparkForge install required)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("etlantic_sparkforge")

from etlantic.plan import explain_plan, plan_pipeline
from etlantic.policy import resolve_validation_policy
from etlantic.reliability import WriteMode
from etlantic.runtime.request import MaterializationPolicy, RetryPolicy, RunIntent
from etlantic.runtime.state import RunStatus
from etlantic_sparkforge import (
    COMPATIBILITY_MATRIX,
    AdapterError,
    SparkForgePipelineSpec,
    adapt_pipeline,
    adapt_run_result,
    assert_delta_capabilities,
    debug_request_from_sparkforge,
    enrich_plan,
    intent_from_sparkforge,
    report_to_sparkforge_explain,
    retry_policy_from_sparkforge,
    selection_from_sparkforge,
    write_mode_from_sparkforge,
    write_mode_metadata,
)

pytestmark = pytest.mark.sparkforge

FIXTURES = Path(__file__).parent / "fixtures"


def _load_ecommerce() -> SparkForgePipelineSpec:
    data = json.loads((FIXTURES / "ecommerce.json").read_text(encoding="utf-8"))
    return SparkForgePipelineSpec.from_dict(data)


def test_adapt_ecommerce_pipeline_parity() -> None:
    spec = _load_ecommerce()
    result = adapt_pipeline(spec)
    graph = result.pipeline_cls.inspect()
    names = [n.name for n in graph.nodes]
    expected = spec.metadata["expected_node_order"]
    assert names == expected
    assert result.layer_by_node["orders"] == "bronze"
    assert result.layer_by_node["clean_orders"] == "silver"
    assert result.layer_by_node["order_kpis"] == "gold"
    # Core graph kinds are never medallion enums.
    assert all(n.kind.value in {"source", "step", "sink"} for n in graph.nodes)
    report = result.pipeline_cls.validate(profile=result.profile)
    assert report.valid


def test_dependency_closure_and_plan_explain() -> None:
    result = adapt_pipeline(_load_ecommerce())
    plan = plan_pipeline(result.pipeline_cls, profile=result.profile)
    assert plan is not None
    explained = explain_plan(plan)
    assert explained["plan_id"] == plan.plan_id
    assert explained["fingerprint"] == plan.fingerprint
    assert isinstance(explained["steps"], list)
    assert explained["steps"]
    assert plan.logical_graph.nodes


def test_write_intent_parity() -> None:
    result = adapt_pipeline(_load_ecommerce())
    by_subject = {w.subject_id: w.mode for w in result.write_intents}
    assert by_subject["silver_orders"] is WriteMode.OVERWRITE
    assert by_subject["gold_order_kpis"] is WriteMode.MERGE
    expected = _load_ecommerce().metadata["expected_write_modes"]
    assert by_subject["silver_orders"].value == expected["silver_orders"]
    assert by_subject["gold_order_kpis"].value == expected["gold_order_kpis"]


def test_validation_policy_thresholds() -> None:
    result = adapt_pipeline(_load_ecommerce())
    meta = result.validation_policy.metadata
    assert meta["min_accept_rate_ingest"] == 90.0
    assert meta["min_accept_rate_clean"] == 95.0
    assert meta["min_accept_rate_publish"] == 98.0


def test_runtime_mapping() -> None:
    assert intent_from_sparkforge("initial_load") is RunIntent.INITIALIZE
    assert intent_from_sparkforge("incremental") is RunIntent.INCREMENTAL
    assert intent_from_sparkforge("validation_only") is RunIntent.VALIDATE
    assert selection_from_sparkforge(run_until="clean_orders").kind == "until"
    assert selection_from_sparkforge(run_one="orders").kind == "only"
    req = debug_request_from_sparkforge(mode="full_refresh", skip_writes=True)
    assert req.intent is RunIntent.REFRESH
    assert req.no_write is True
    assert req.materialization is MaterializationPolicy.DEFAULT
    validate_req = debug_request_from_sparkforge(mode="validation_only")
    assert validate_req.intent is RunIntent.VALIDATE
    assert validate_req.no_write is True
    assert validate_req.materialization is MaterializationPolicy.DEFAULT


def test_report_normalization_and_redaction() -> None:
    payload = {
        "status": "succeeded",
        "pipeline": "ecommerce",
        "run_id": "sf-1",
        "mode": "incremental",
        "password": "should-not-leak",
        "steps": [
            {
                "name": "orders",
                "status": "failed",
                "records_out": 10,
                "error": "password=hunter2 connect failed",
                "note": "Authorization: Bearer abc123token",
            },
            {
                "name": "clean_orders",
                "status": "succeeded",
                "records_out": 9,
                "dsn": "postgresql://u:secretpass@host/db",
            },
        ],
        "validations": [
            {
                "step": "orders",
                "status": "passed",
                "total": 10,
                "invalid": 0,
                "message": "https://user:leakpass@api.example/path",
            }
        ],
        "tables": [{"table": "silver_orders", "count": 9}],
        "secrets": {"api_key": "xyz"},
        "diagnostics": [
            {"code": "X", "message": "token=supersecret"},
            "mongodb://ada:hunter2@db/app",
        ],
    }
    report = adapt_run_result(payload)
    dumped = report.to_dict()
    text = json.dumps(dumped)
    for secret in (
        "should-not-leak",
        "xyz",
        "hunter2",
        "abc123token",
        "secretpass",
        "leakpass",
        "supersecret",
    ):
        assert secret not in text
    assert report.status.value == "succeeded"
    assert len(report.steps) == 2
    assert report.intent is RunIntent.INCREMENTAL
    explain = report_to_sparkforge_explain(report)
    assert explain["run_id"] == "sf-1"
    assert explain["mode"] == "incremental"
    assert "hunter2" not in json.dumps(explain)


def test_delta_fail_closed_without_capabilities() -> None:
    diags = assert_delta_capabilities(["merge", "vacuum"])
    assert any(d.code == "PMSF322" for d in diags)
    assert all(d.severity.value == "error" for d in diags)


def test_delta_missing_capability_respects_strict() -> None:
    from etlantic.capabilities import PluginCapabilities

    caps = PluginCapabilities(engine="pyspark", spark=True)
    strict = assert_delta_capabilities(["merge"], capabilities=caps, strict=True)
    assert any(d.code == "PMSF323" and d.severity.value == "error" for d in strict)
    soft = assert_delta_capabilities(["merge"], capabilities=caps, strict=False)
    assert any(d.code == "PMSF323" and d.severity.value == "warning" for d in soft)


def test_missing_step_name_emits_diagnostic() -> None:
    spec, diags = SparkForgePipelineSpec.parse(
        {
            "name": "missing_name",
            "steps": [{"kind": "bronze_rules", "layer": "bronze"}],
        }
    )
    assert any(d.code == "PMSF310" for d in diags)
    assert spec.steps == ()


def test_delta_ops_in_spec_fail_adapt() -> None:
    data = json.loads((FIXTURES / "ecommerce.json").read_text(encoding="utf-8"))
    data["metadata"] = {**data.get("metadata", {}), "delta_operations": ["merge"]}
    spec = SparkForgePipelineSpec.from_dict(data)
    with pytest.raises(AdapterError) as exc:
        adapt_pipeline(spec)
    assert exc.value.code == "PMSF320"


def test_cycle_fail_closed() -> None:
    data = {
        "name": "cyclic",
        "steps": [
            {
                "name": "a",
                "kind": "silver_transform",
                "layer": "silver",
                "source": "b",
            },
            {
                "name": "b",
                "kind": "silver_transform",
                "layer": "silver",
                "source": "a",
            },
        ],
    }
    with pytest.raises(AdapterError):
        adapt_pipeline(SparkForgePipelineSpec.from_dict(data))


def test_compatibility_matrix_present() -> None:
    assert "write" in COMPATIBILITY_MATRIX
    assert write_mode_from_sparkforge("append") is WriteMode.APPEND


def test_core_has_no_medallion_enums() -> None:
    import inspect

    import etlantic

    src = Path(inspect.getfile(etlantic)).parent
    offenders: list[str] = []
    for path in src.rglob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        # Allow comments about SparkForge boundary in docs strings sparingly —
        # fail if identifiers introduce medallion types.
        if "class bronze" in text or "class silver" in text or "class gold" in text:
            offenders.append(str(path))
        if "layerkind" in text or "medallionlayer" in text:
            offenders.append(str(path))
    assert offenders == []


def test_source_based_wiring_respects_reorder() -> None:
    data = {
        "name": "reordered",
        "schema": "demo",
        "engine": "local",
        "steps": [
            {
                "name": "bronze",
                "kind": "bronze_rules",
                "layer": "bronze",
                "table_name": "b",
            },
            {
                "name": "gold",
                "kind": "gold_transform",
                "layer": "gold",
                "source": "silver",
                "table_name": "g",
                "write_mode": "overwrite",
            },
            {
                "name": "silver",
                "kind": "silver_transform",
                "layer": "silver",
                "source": "bronze",
                "table_name": "s",
                "write_mode": "overwrite",
            },
        ],
    }
    result = adapt_pipeline(SparkForgePipelineSpec.from_dict(data))
    graph = result.pipeline_cls.inspect()
    pairs = {(e.producer_node, e.consumer_node) for e in graph.edges}
    assert ("bronze", "silver") in pairs
    assert ("silver", "gold") in pairs


def test_unknown_source_fail_closed() -> None:
    data = {
        "name": "dangling",
        "engine": "local",
        "steps": [
            {
                "name": "bronze",
                "kind": "bronze_rules",
                "layer": "bronze",
            },
            {
                "name": "silver",
                "kind": "silver_transform",
                "layer": "silver",
                "source": "missing",
                "write_mode": "overwrite",
            },
        ],
    }
    with pytest.raises(AdapterError) as exc:
        adapt_pipeline(SparkForgePipelineSpec.from_dict(data))
    assert any(d.code == "PMSF312" for d in exc.value.report.diagnostics)


def test_multi_bronze_source_wiring() -> None:
    data = {
        "name": "multi",
        "engine": "local",
        "steps": [
            {"name": "a", "kind": "bronze_rules", "layer": "bronze"},
            {"name": "b", "kind": "bronze_rules", "layer": "bronze"},
            {
                "name": "from_a",
                "kind": "silver_transform",
                "layer": "silver",
                "source": "a",
                "table_name": "out_a",
                "write_mode": "overwrite",
            },
        ],
    }
    result = adapt_pipeline(SparkForgePipelineSpec.from_dict(data))
    assert "a" in result.step_map
    assert "b" in result.step_map
    edges = result.pipeline_cls.inspect().edges
    assert any(e.producer_node == "a" for e in edges)


def test_unknown_report_status_fail_closed() -> None:
    report = adapt_run_result({"status": "weird_unknown_status", "steps": []})
    assert report.status is RunStatus.FAILED
    assert any(d.code == "PMSF500" for d in report.diagnostics)


def test_report_preserves_zero_counts_and_aliases() -> None:
    report = adapt_run_result(
        {
            "status": "timeout",
            "started_at": "2026-01-01T00:00:00+00:00",
            "ended_at": "2026-01-01T00:00:05+00:00",
            "records_in": 0,
            "records_out": 0,
            "steps": [
                {
                    "name": "a",
                    "status": "skipped",
                    "attempts": 0,
                    "records_in": 0,
                    "records_out": 0,
                },
                {"name": "b", "status": "canceled"},
            ],
        }
    )
    assert report.status is RunStatus.TIMED_OUT
    assert report.summary.records_in == 0
    assert report.summary.records_out == 0
    assert report.summary.skipped == 1
    assert report.summary.cancelled == 1
    assert report.steps[0].attempts == 0
    assert report.steps[0].records_in == 0
    assert report.ended_at is not None
    assert report.duration_seconds == 5.0


def test_retry_policy_maps_to_core() -> None:
    policy = retry_policy_from_sparkforge(
        {"retries": 3, "delay": 1.5, "retry_on": ["TimeoutError"]}
    )
    assert isinstance(policy, RetryPolicy)
    assert policy.max_attempts == 3
    assert policy.backoff_seconds == 1.5
    assert policy.retry_on == ("TimeoutError",)
    req = debug_request_from_sparkforge(
        mode="standard", retry={"max_attempts": 2, "backoff_seconds": 0.5}
    )
    assert req.retry.max_attempts == 2
    assert req.retry.backoff_seconds == 0.5


def test_bad_write_mode_adapter_error() -> None:
    data = {
        "name": "bad_write",
        "engine": "local",
        "steps": [
            {"name": "bronze", "kind": "bronze_rules", "layer": "bronze"},
            {
                "name": "silver",
                "kind": "silver_transform",
                "layer": "silver",
                "source": "bronze",
                "write_mode": "truncate",
            },
        ],
    }
    with pytest.raises(AdapterError) as exc:
        adapt_pipeline(SparkForgePipelineSpec.from_dict(data))
    assert any(d.code == "PMSF307" for d in exc.value.report.diagnostics)


def test_overwrite_partitions_metadata() -> None:
    meta = write_mode_metadata("overwrite_partitions")
    assert meta["partition_overwrite"] is True
    assert write_mode_from_sparkforge("overwrite_partitions") is WriteMode.OVERWRITE


def test_registered_validation_policy_resolves() -> None:
    result = adapt_pipeline(_load_ecommerce())
    resolved = resolve_validation_policy(result.profile.validation_policy)
    assert resolved.metadata["min_accept_rate_ingest"] == 90.0
    assert resolved.name == result.validation_policy.name


def test_enrich_plan_write_intents() -> None:
    result = adapt_pipeline(_load_ecommerce())
    plan = plan_pipeline(result.pipeline_cls, profile=result.profile)
    enriched = enrich_plan(plan, result)
    intents = enriched.intents["write_intents"]
    assert intents["gold_order_kpis"]["intent"] == "merge"
    assert intents["silver_orders"]["mode"] == "overwrite"


def test_delta_plan_only_warns() -> None:
    data = json.loads((FIXTURES / "ecommerce.json").read_text(encoding="utf-8"))
    data["metadata"] = {**data.get("metadata", {}), "delta_operations": ["merge"]}
    result = adapt_pipeline(SparkForgePipelineSpec.from_dict(data), strict_delta=False)
    assert any(
        d.code == "PMSF322" and d.severity.value == "warning"
        for d in result.diagnostics
    )
    assert "spark_delta" in result.profile.required_spark_capabilities


def test_zero_accept_rates_preserved() -> None:
    spec = SparkForgePipelineSpec.from_dict(
        {
            "name": "zero",
            "min_bronze_rate": 0.0,
            "min_silver_rate": 0.0,
            "min_gold_rate": 0.0,
            "steps": [{"name": "a", "kind": "bronze_rules", "layer": "bronze"}],
        }
    )
    assert spec.min_bronze_rate == 0.0
    assert spec.min_silver_rate == 0.0


def test_no_write_skips_sink_node() -> None:
    data = {
        "name": "nowrite",
        "engine": "local",
        "steps": [
            {"name": "bronze", "kind": "bronze_rules", "layer": "bronze"},
            {
                "name": "silver",
                "kind": "silver_transform",
                "layer": "silver",
                "source": "bronze",
                "write_mode": "no_write",
            },
        ],
    }
    result = adapt_pipeline(SparkForgePipelineSpec.from_dict(data))
    names = [n.name for n in result.pipeline_cls.inspect().nodes]
    assert "silver" in names
    assert "silver_out" not in names
    assert result.write_intents[0].mode is WriteMode.NO_WRITE
