"""Sol verification for unresolved ETLantic 0.52 release blockers.

These tests intentionally fail until the production implementation satisfies
the approved adaptive-planning contract.  They exercise public behavior except
where a static release-gate assertion is the contract under review.
"""

from __future__ import annotations

import copy
import hashlib
import inspect
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import get_type_hints

import anyio
import pytest

from etlantic import Data, Extract, Input, Load, Output, Pipeline, Transformation
from etlantic.exceptions import PipelineExecutionError, PipelineValidationError
from etlantic.orchestration import compile_plan
from etlantic.plan import (
    AdaptiveDecision,
    diff_plans,
    explain_plan,
    plan_from_json,
    plan_pipeline,
    plan_pipeline_with_report,
    plan_to_json,
    verify_plan_fingerprint,
)
from etlantic.plan.adaptive_model import CandidateRecord
from etlantic.plan.adaptive_serialize import adaptive_plan_fingerprint
from etlantic.profile import PlacementTarget, Profile
from etlantic.registry import PlanningContext, PluginDescriptor, builtin_stub_registry
from etlantic.runtime.execute import arun_pipeline

ROOT = Path(__file__).resolve().parents[2]


class Row(Data):
    id: int


class Sample(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    out: Load[Row] = Load(input=raw, asset="out")


_PORTABLE_CALLS = {"user": 0}


class PortableIdentity(Transformation):
    source: Input[Row]
    result: Output[Row]


@PortableIdentity.portable
def _portable_identity(source):
    _PORTABLE_CALLS["user"] += 1
    return source.select("id")


class PortableSample(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    normalized = PortableIdentity.step(source=raw)
    out: Load[Row] = Load(input=normalized.result, asset="out")


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


def test_adaptive_solver_oracle_rejects_a_nonoptimal_assignment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The independent exhaustive oracle remains an active fail-closed gate."""

    def choose_remote(
        graph: object,
        candidates: tuple[CandidateRecord, ...],
        targets: tuple[tuple[str, object, object], ...],
        context: PlanningContext,
    ) -> tuple[AdaptiveDecision, ...]:
        del targets, context
        nodes = graph.node_names()  # type: ignore[attr-defined]
        chosen = {
            candidate.node_name: candidate
            for candidate in candidates
            if candidate.status == "eligible" and candidate.target_id == "remote"
        }
        return tuple(
            AdaptiveDecision(node, chosen[node].candidate_id, "remote")
            for node in nodes
        )

    monkeypatch.setattr("etlantic.planning.adaptive._solve", choose_remote)
    profile = _profile(
        placement_targets={
            "local": PlacementTarget(engine="local", location="local"),
            "remote": PlacementTarget(engine="local", location="remote"),
        },
        eligible_targets=("local", "remote"),
    )
    with pytest.raises(PipelineValidationError, match="PMADP306"):
        plan_pipeline(Sample, profile=profile)


def test_adaptive_solver_matches_seeded_oracle_corpus() -> None:
    """Small deterministic cases exercise solver/oracle agreement with replay seeds."""
    for seed in range(16):
        first_location = "local" if seed & 1 else "remote"
        second_location = "remote" if seed & 1 else "local"
        order = ("first", "second") if seed & 2 else ("second", "first")
        targets = {
            "first": PlacementTarget(engine="local", location=first_location),
            "second": PlacementTarget(engine="local", location=second_location),
        }
        if seed & 4:
            targets = dict(reversed(tuple(targets.items())))
        try:
            plan_pipeline(
                Sample,
                profile=_profile(
                    placement_targets=targets,
                    eligible_targets=order,
                ),
            )
        except Exception as exc:  # pragma: no cover - failure retains replay seed
            pytest.fail(f"adaptive oracle corpus seed={seed}: {exc!r}")


def test_adaptive_bytes_ignore_target_mapping_insertion_order() -> None:
    """Equivalent target-map insertion orders produce identical canonical bytes."""
    targets = {
        "first": PlacementTarget(engine="local", location="local"),
        "second": PlacementTarget(engine="local", location="remote"),
    }
    forward = plan_pipeline(
        Sample,
        profile=_profile(
            placement_targets=targets,
            eligible_targets=("first", "second"),
        ),
    )
    reverse = plan_pipeline(
        Sample,
        profile=_profile(
            placement_targets=dict(reversed(tuple(targets.items()))),
            eligible_targets=("first", "second"),
        ),
    )
    assert plan_to_json(forward, indent=None) == plan_to_json(reverse, indent=None)


def test_adaptive_resource_limits_fail_before_crossing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deterministic memory and solver limits fail closed at the boundary."""
    monkeypatch.setattr("etlantic.planning.adaptive.MAX_TRANSIENT_BYTES", 1)
    with pytest.raises(PipelineValidationError, match="PMADP303"):
        plan_pipeline(Sample, profile=_profile())

    monkeypatch.setattr("etlantic.planning.adaptive.MAX_TRANSIENT_BYTES", 256 << 20)
    monkeypatch.setattr("etlantic.planning.adaptive.MAX_SOLVER_EXPANSIONS", 0)
    with pytest.raises(PipelineValidationError, match="PMADP304"):
        plan_pipeline(Sample, profile=_profile())


def test_adaptive_candidate_analysis_is_analyze_only() -> None:
    """Planning uses cached portable IR and compiler analyze(), never user/runtime code."""
    from etlantic.transform.local_compiler import LocalTransformCompiler

    calls = {"analyze": 0, "compile": 0, "execute": 0, "user": 0}
    _PORTABLE_CALLS["user"] = 0
    delegate = LocalTransformCompiler()

    class CompilerSentinel:
        @property
        def info(self):
            return delegate.info

        def analyze(self, *args: object, **kwargs: object):
            calls["analyze"] += 1
            return delegate.analyze(*args, **kwargs)  # type: ignore[arg-type]

        def compile(self, *args: object, **kwargs: object) -> object:
            del args, kwargs
            calls["compile"] += 1
            raise AssertionError("compile reached during adaptive planning")

        async def execute(self, *args: object, **kwargs: object) -> object:
            del args, kwargs
            calls["execute"] += 1
            raise AssertionError("execute reached during adaptive planning")

    registry = builtin_stub_registry()
    registry.register_transform_compiler("local", CompilerSentinel())
    context = PlanningContext.create(profile=_profile(), registry=registry)

    plan = plan_pipeline(PortableSample, context=context)

    assert plan.schema == "etlantic.plan/2"
    calls["user"] = _PORTABLE_CALLS["user"]
    assert calls == {"analyze": 1, "compile": 0, "execute": 0, "user": 0}


def test_adaptive_explain_uses_the_bounded_summary() -> None:
    """Oversized stored evidence returns PMADP305 without replanning."""
    plan = plan_pipeline(Sample, profile=_profile())
    candidates = []
    for index, candidate in enumerate(plan.candidates):
        oversized_candidate = copy.copy(candidate)
        object.__setattr__(
            oversized_candidate,
            "metadata",
            {"etlantic.release-padding": f"{index}-" + "x" * (2 * 1024 * 1024)},
        )
        candidates.append(oversized_candidate)
    # Candidate metadata is deliberately expanded after construction so the
    # test can exercise the explain projection without spending minutes in the
    # independent metadata-hardening scan.  No planner or I/O path is bypassed.
    oversized = copy.copy(plan)
    object.__setattr__(oversized, "candidates", tuple(candidates))

    explanation = explain_plan(oversized)

    assert explanation["truncated"] is True
    assert explanation["diagnostic"]["code"] == "PMADP305"
    assert len(json.dumps(explanation).encode("utf-8")) < 4 * 1024 * 1024


def test_adaptive_diff_covers_semantic_and_cross_schema_changes() -> None:
    """Adaptive diff classifies assignment/topology and schema boundaries."""
    left = plan_pipeline(Sample, profile=_profile())
    right = plan_pipeline(
        Sample,
        profile=_profile(
            placement_targets={"other": PlacementTarget(engine="local")},
            eligible_targets=("other",),
        ),
    )
    changed = diff_plans(left, right).to_dict()["changed_adaptive"]
    assert any(item.get("classification") == "semantic" for item in changed)
    explicit = plan_pipeline(Sample, profile="local")
    cross_schema = diff_plans(explicit, left).to_dict()["changed_adaptive"]
    assert cross_schema == [
        {
            "classification": "semantic",
            "schema": {"left": "etlantic.plan/1", "right": "etlantic.plan/2"},
        }
    ]


def test_adaptive_regions_are_maximal_and_unfused_without_proof() -> None:
    """Connected same-target nodes share one deterministic unfused region."""
    plan = plan_pipeline(Sample, profile=_profile())
    assert len(plan.regions) == 1
    assert plan.regions[0].logical_nodes == ("raw", "out")
    assert plan.regions[0].fused is False


def test_adaptive_logical_path_can_cross_all_boundary_unit_kinds() -> None:
    """Every non-compute physical kind can participate in a validated path."""
    from etlantic.plan.physical import (
        PhysicalDAG,
        PhysicalDependency,
        PhysicalUnit,
        PhysicalUnitKind,
    )

    kinds = (
        PhysicalUnitKind.TRANSFER,
        PhysicalUnitKind.COLLECTION,
        PhysicalUnitKind.VALIDATION,
        PhysicalUnitKind.MATERIALIZATION,
        PhysicalUnitKind.REUSE,
    )
    units = [
        PhysicalUnit(
            identity="source-compute",
            kind=PhysicalUnitKind.COMPUTE,
            target_identity="target-1",
            logical_nodes=("raw",),
        )
    ]
    predecessor = "source-compute"
    for kind in kinds:
        identity = f"boundary-{kind.value}"
        units.append(
            PhysicalUnit(
                identity=identity,
                kind=kind,
                dependencies=(PhysicalDependency(predecessor),),
                target_identity="target-1",
            )
        )
        predecessor = identity
    units.extend(
        (
            PhysicalUnit(
                identity="sink-compute",
                kind=PhysicalUnitKind.COMPUTE,
                dependencies=(PhysicalDependency(predecessor),),
                target_identity="target-1",
                logical_nodes=("out",),
            ),
            PhysicalUnit(
                identity="publication",
                kind=PhysicalUnitKind.PUBLICATION,
                dependencies=(PhysicalDependency("sink-compute", "lifecycle"),),
                target_identity="target-1",
            ),
        )
    )
    dag = PhysicalDAG(
        units=tuple(units),
        logical_to_physical={"raw": "source-compute", "out": "sink-compute"},
        topological_order=tuple(unit.identity for unit in units),
    )
    dag.validate_logical_paths((("raw", "out"),))
    assert {unit.kind for unit in dag.units} == set(PhysicalUnitKind)


def test_adaptive_surface_projections_share_plan_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Python, CLI-style, notebook, and IDE projections share one identity."""
    from etlantic.cli.cmds.core import render_plan_explain_human
    from etlantic.ide.commands import execute_command
    from etlantic.ide.protocol import IdeCommand

    profile = _profile()
    python_plan = plan_pipeline(Sample, profile=profile)
    class_plan = Sample.plan(profile=profile)
    assert class_plan.fingerprint == python_plan.fingerprint
    wire = json.loads(plan_to_json(python_plan))
    explanation = explain_plan(python_plan)
    human = render_plan_explain_human(explanation)
    assert wire["fingerprint"] == explanation["fingerprint"]
    assert wire["plan_id"] in human

    monkeypatch.setattr(
        "etlantic.ide.commands._resolve_target",
        lambda *args, **kwargs: Sample,
    )
    result = execute_command(
        IdeCommand(name="plan", arguments={"target": "sample", "profile": profile})
    )
    assert result.ok
    assert result.payload["fingerprint"] == python_plan.fingerprint


def test_adaptive_release_side_effect_sentinels(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Emit measured zero side-effect counts for the evidence generator."""
    counts = {"compile": 0, "execute": 0, "io": 0}
    plan = plan_pipeline(Sample, profile=_profile())

    def unexpected_compile_discovery(*args: object, **kwargs: object) -> object:
        del args, kwargs
        counts["compile"] += 1
        raise AssertionError("compile discovery reached")

    monkeypatch.setattr(
        "etlantic.orchestration.compile.discover_orchestrator_plugins",
        unexpected_compile_discovery,
    )
    with pytest.raises(ValueError, match="PMADP500"):
        compile_plan(plan, target="airflow")  # type: ignore[arg-type]

    class RuntimeSentinel:
        def __getattribute__(self, name: str) -> object:
            counts["io"] += 1
            raise AssertionError(f"runtime access reached: {name}")

    async def execute() -> None:
        try:
            await arun_pipeline(
                Sample,
                profile=_profile(),
                runtime=RuntimeSentinel(),  # type: ignore[arg-type]
            )
        except PipelineExecutionError as exc:
            assert exc.code == "PMADP500"
        else:
            raise AssertionError("adaptive execution was accepted")

    anyio.run(execute)
    assert counts == {"compile": 0, "execute": 0, "io": 0}
    with capsys.disabled():
        print(
            "ETLANTIC_ADAPTIVE_SIDE_EFFECT_COUNTS=" + json.dumps(counts, sort_keys=True)
        )


def test_adaptive_release_evidence_contract_is_ci_gated() -> None:
    """Every platform row executes the same non-writing evidence verifier."""
    workflow = (ROOT / ".github/workflows/checks.yml").read_text(encoding="utf-8")
    assert "os: [ubuntu-latest, windows-latest, macos-latest]" in workflow
    assert 'python-version: ["3.11", "3.12", "3.13"]' in workflow
    step = workflow.split("- name: Adaptive 0.52 evidence verifier", 1)[1].split(
        "- name:", 1
    )[0]
    assert "if:" not in step
    assert "scripts/check_adaptive_0_52.py" in step


def test_final_052_012_logical_edge_path_cannot_be_hidden_by_metadata() -> None:
    """Logical edges are authoritative even after a fingerprint is recomputed."""
    plan = plan_pipeline(Sample, profile=_profile())
    data = plan.to_dict()
    consumer_id = data["physical_dag"]["logical_to_physical"]["out"]
    consumer = next(
        unit
        for unit in data["physical_dag"]["units"]
        if unit["identity"] == consumer_id
    )
    consumer["dependencies"] = []
    consumer["metadata"]["etlantic.logical_predecessors"] = []
    canonical = dict(data)
    canonical.pop("fingerprint")
    canonical.pop("plan_id")
    fingerprint = hashlib.sha256(
        json.dumps(
            canonical,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    data["fingerprint"] = fingerprint
    data["plan_id"] = f"plan:{fingerprint[:16]}"

    with pytest.raises(ValueError, match=r"PMADP403.*has no physical dependency path"):
        plan_from_json(json.dumps(data, sort_keys=True))
