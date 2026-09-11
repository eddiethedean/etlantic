"""Sol verification for unresolved ETLantic 0.52 release blockers.

These tests intentionally fail until the production implementation satisfies
the approved adaptive-planning contract.  They exercise public behavior except
where a static release-gate assertion is the contract under review.
"""

from __future__ import annotations

import inspect
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import get_type_hints

import pytest

from etlantic import Data, Extract, Load, Pipeline
from etlantic.exceptions import PipelineValidationError
from etlantic.plan import (
    diff_plans,
    plan_pipeline,
    plan_pipeline_with_report,
    verify_plan_fingerprint,
)
from etlantic.plan.adaptive_model import CandidateRecord
from etlantic.plan.adaptive_serialize import adaptive_plan_fingerprint
from etlantic.profile import PlacementTarget, Profile
from etlantic.registry import PlanningContext, PluginDescriptor, builtin_stub_registry

ROOT = Path(__file__).resolve().parents[2]


class Row(Data):
    id: int


class Sample(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    out: Load[Row] = Load(input=raw, asset="out")


def _profile(**updates: object) -> Profile:
    values: dict[str, object] = {
        "name": "review-adaptive",
        "execution_strategy": "adaptive",
        "portable_transform_policy": "require",
        "placement_targets": {"local": PlacementTarget(engine="local")},
        "eligible_targets": ("local",),
    }
    values.update(updates)
    return Profile(**values)  # type: ignore[arg-type]


def test_final_052_001_missing_target_reference_is_negative() -> None:
    """An unresolved connector cannot inherit engine availability."""
    profile = _profile(
        placement_targets={
            "local": PlacementTarget(
                engine="local", connector="connector-that-is-not-installed"
            )
        }
    )
    with pytest.raises(PipelineValidationError, match="PMADP320"):
        plan_pipeline(Sample, profile=profile)


def test_final_052_001_target_limit_precedes_plugin_discovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The eight-target limit must fail before adaptive discovery."""
    calls = 0

    def discovered(
        *args: object, **kwargs: object
    ) -> tuple[list[object], list[object]]:
        nonlocal calls
        del args, kwargs
        calls += 1
        return [], []

    monkeypatch.setattr(
        "etlantic.plugins.coordinator.discover_planning_plugins", discovered
    )
    targets = {
        f"target-{index}": PlacementTarget(
            engine="pandas", location=f"location-{index}"
        )
        for index in range(9)
    }
    profile = _profile(placement_targets=targets, eligible_targets=tuple(targets))
    with pytest.raises(PipelineValidationError, match="PMADP100"):
        plan_pipeline(Sample, profile=profile)
    assert calls == 0


def test_final_052_001_node_limit_precedes_plugin_discovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The selected-node limit must fail before adaptive discovery."""
    calls = 0

    def discovered(
        *args: object, **kwargs: object
    ) -> tuple[list[object], list[object]]:
        nonlocal calls
        del args, kwargs
        calls += 1
        return [], []

    monkeypatch.setattr(
        "etlantic.plugins.coordinator.discover_planning_plugins", discovered
    )
    attrs: dict[str, object] = {"__module__": __name__, "__annotations__": {}}
    annotations = attrs["__annotations__"]
    assert isinstance(annotations, dict)
    for index in range(257):
        name = f"source_{index:03d}"
        annotations[name] = Extract[Row]
        attrs[name] = Extract(asset=name)
    oversized = type("OversizedReviewPipeline", (Pipeline,), attrs)
    with pytest.raises(PipelineValidationError, match="PMADP300"):
        plan_pipeline(oversized, profile=_profile())
    assert calls == 0


def test_final_052_002_generic_engine_pair_is_not_handoff_evidence() -> None:
    """Handoff proof must bind the full edge contract, not just engine names."""
    profile = _profile(
        placement_targets={
            "producer": PlacementTarget(engine="local"),
            "consumer": PlacementTarget(engine="null"),
        },
        eligible_targets=("producer", "consumer"),
        implementation_overrides={"raw": "producer", "out": "consumer"},
    )
    registry = builtin_stub_registry()
    registry.register_plugin(
        PluginDescriptor(
            name="generic-handoff",
            kind="runtime",
            version="1",
            metadata={"handoff_evidence": {"local->null": "generic-engine-pair-only"}},
        )
    )
    context = PlanningContext.create(profile=profile, registry=registry)
    with pytest.raises(PipelineValidationError, match="PMADP320"):
        plan_pipeline(Sample, context=context)


def test_final_052_003_fallback_report_and_integrity() -> None:
    """Fallback must report its reason and return a verified independent `/1`."""
    profile = _profile(
        adaptive_fallback="explicit",
        placement_targets={
            "local": PlacementTarget(
                engine="local", required_capabilities=("unsupported.review",)
            )
        },
    )
    plan, report = plan_pipeline_with_report(Sample, profile=profile)
    assert plan is not None and plan.schema == "etlantic.plan/1"
    assert report.has_errors
    assert any(d.code == "PMADP320" for d in report.diagnostics)
    verify_plan_fingerprint(plan)


def test_final_052_003_fallback_plan_fingerprint_is_valid() -> None:
    """Adding fallback provenance must not invalidate the returned `/1` plan."""
    profile = _profile(
        adaptive_fallback="explicit",
        placement_targets={
            "local": PlacementTarget(
                engine="local", required_capabilities=("unsupported.review",)
            )
        },
    )
    plan, _ = plan_pipeline_with_report(Sample, profile=profile)
    assert plan is not None and plan.schema == "etlantic.plan/1"
    verify_plan_fingerprint(plan)


def test_final_052_005_checkout_root_is_not_a_canonical_input() -> None:
    """Equivalent checkout-local references produce identical plan identity."""
    left = _profile(
        placement_targets={
            "local": PlacementTarget(
                engine="local", resource="/checkout-one/etlantic/plugins/provider"
            )
        }
    )
    right = _profile(
        placement_targets={
            "local": PlacementTarget(
                engine="local", resource="/checkout-two/etlantic/plugins/provider"
            )
        }
    )
    assert (
        plan_pipeline(Sample, profile=left).fingerprint
        == plan_pipeline(Sample, profile=right).fingerprint
    )


def test_final_052_006_evidence_regenerates_cleanly() -> None:
    """Committed adaptive evidence must regenerate from the current revision."""
    check = subprocess.run(
        [sys.executable, "scripts/check_adaptive_0_52.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert check.returncode == 0, check.stdout + check.stderr


def test_final_052_006_evidence_covers_acceptance_ledger() -> None:
    """Generated scenarios must cover every 0.52 acceptance criterion."""
    evidence_dir = ROOT / "docs/11_DEVELOPMENT/evidence/adaptive_0_51"
    covered: set[str] = set()
    for path in evidence_dir.glob("adaptive_*_0_51.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for scenario in payload.get("scenarios", []):
            covered.add(str(scenario.get("acceptance_criterion")))
    assert covered >= {f"AC-052-{index:03d}" for index in range(1, 19)}


def test_final_052_006_evidence_is_ci_gated() -> None:
    """CI must execute the adaptive evidence checker before release."""
    workflows = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / ".github/workflows").glob("*.yml")
    )
    assert "check_adaptive_0_52.py" in workflows


def test_final_052_007_solver_handles_prunable_in_scope_plan() -> None:
    """The required exact branch-and-bound solver must prune obvious losers."""
    attrs: dict[str, object] = {"__module__": __name__, "__annotations__": {}}
    annotations = attrs["__annotations__"]
    assert isinstance(annotations, dict)
    for index in range(20):
        name = f"source_{index:02d}"
        annotations[name] = Extract[Row]
        attrs[name] = Extract(asset=name)
    wide = type("WideReviewPipeline", (Pipeline,), attrs)
    profile = _profile(
        placement_targets={
            "preferred": PlacementTarget(engine="local", location="local"),
            "dominated": PlacementTarget(engine="local", location="remote"),
        },
        eligible_targets=("preferred", "dominated"),
    )
    plan = plan_pipeline(wide, profile=profile)
    assert len(plan.decisions) == 20
    assert {decision.target_id for decision in plan.decisions} == {"preferred"}


def test_final_052_008_diff_classifies_evidence_only_change() -> None:
    """An evidence-only change is explanatory, not a semantic plan change."""
    left = plan_pipeline(Sample, profile=_profile())
    candidate_data = left.candidates[0].to_dict()
    candidate_data["evidence_refs"].append("review:evidence-only")
    changed_candidate = CandidateRecord.from_dict(candidate_data)
    right = replace(left, candidates=(changed_candidate, *left.candidates[1:]))
    right = replace(
        right,
        fingerprint=adaptive_plan_fingerprint(right),
        plan_id="plan:pending",
    )
    right = replace(right, plan_id=f"plan:{right.fingerprint[:16]}")
    payload = diff_plans(left, right).to_dict()
    encoded = json.dumps(payload, sort_keys=True)
    assert "explanatory" in encoded
    assert "semantic" not in encoded


def test_final_052_009_public_planning_types_use_plan_document() -> None:
    """Public class and preview APIs expose the `/1`-or-`/2` union."""
    from etlantic.authoring.preview import plan_preview

    pipeline_return = inspect.signature(inspect.unwrap(Pipeline.plan)).return_annotation
    preview_return = get_type_hints(plan_preview)["return"]
    assert pipeline_return == "PlanDocument"
    assert "AdaptivePipelinePlan" in str(preview_return)
    assert "PipelinePlan" in str(preview_return)
