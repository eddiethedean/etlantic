# Sol Production Re-review — Phase 0.53

Reviewed HEAD: `637aebb83dd6563b790a6b76cac8b595af7ae60a`.

The binding remediation works, but FINAL-004 remains partially fixed. The approved contract requires effective parameter, binding, and implementation overrides before validation and candidate construction. This review adds only a protected verification artifact and this report; production implementation, existing Sol verification, configuration, and committed evidence remain unchanged. The pre-existing untracked `SOL_PRODUCTION_REREVIEW_1012f3ec.md` is preserved.

## Contract and scope integrity

Authority: `docs/11_DEVELOPMENT/IMPLEMENTATION_PLAN_0_53.md`, especially lines 134–143 and AC-003/AC-007; ADR-025 lines 69–80 specifies request implementation overrides before Profile overrides. The release boundary remains Experimental, fixture-qualified local adaptive physical-DAG execution, five qualified families, captured descriptors, atomic admission, lifecycle/report/privacy guarantees, and explicit `/1` compatibility. Durable/remote execution, arbitrary topologies, additional backend qualification, and repository-wide cleanup remain excluded.

The current binding patch is within this boundary. It overlays immutable graph bindings before candidate construction and runtime binding capture. No dependency, CI, or public contract expansion was introduced by the patch. Merely serializing a request does not satisfy its effective-input requirements.

## FINAL-004 — Effective parameter and implementation overrides still do not control planning

Severity: High

Disposition: BLOCKER

Related AC: AC-003, AC-007

Location:

- `src/etlantic/plan/planner.py:197–205`, public class planning validation.
- `src/etlantic/planning/adaptive.py:165–173`, override target validation.
- `src/etlantic/planning/adaptive.py:867–892`, candidate target restriction.

Problem: The public class planner validates the authored pipeline before applying request parameters. The adaptive planner validates and restricts candidate targets using only `Profile.implementation_overrides`. `RunRequest.implementation_overrides` is ignored during both operations. Binding normalization resolves only one part of the previously identified effective-request root cause.

Evidence: Three protected tests in `tests/runtime/test_sol_0_53_effective_request.py` fail at this HEAD:

1. `test_final_004_request_implementation_override_precedes_profile`: two distinct, eligible local target identities are supplied. Profile selects `first`, request selects `second`; the actual plan selects `first` for both nodes.
2. `test_final_004_unknown_request_implementation_override_rejects`: request names `unqualified`; planning succeeds instead of rejecting with `PMADP121`.
3. `test_final_004_required_parameter_override_precedes_validation`: request supplies the required portable filter parameter. Public `arun_pipeline` rejects authored validation with `PMTRN102`, before executing the filter.

Targeted run: **3 failed in 2.51s**, expected contract failures. The same filter and qualified local topology succeed with author-bound parameter `minimum_id=2`, yielding IDs `[2, 3]`. Thus the parameter reproducer does not depend on an unsupported kernel or topology.

Relationship to current change: These are unfulfilled parts of the existing FINAL-004 effective-request requirement, not new scope or three new findings. This review retains its original FINAL ID despite an implementation report calling it SOL-004.

Why it matters: Accepted requests can silently persist placement contrary to user overrides, accept unknown placement constraints, or reject a valid request supplying a required parameter.

Why this blocks the current change: AC-003 requires identical effective inputs across planning variants; AC-007 explicitly requires overrides before planning without widening eligibility. The changed adaptive functionality cannot meet that public contract while request overrides are ignored or applied after validation. Green binding smoke tests do not prove these requirements.

Required behavior: Normalize effective request inputs before authored validation and adaptive candidate construction across the supported public planning/execution variants. Apply request target overrides before Profile overrides, restrict only already eligible trusted portable targets, reject unknown override targets with `PMADP121`, and allow request-provided required parameters to validate and execute. Preserve explicit `/1` behavior, immutable binding authority, stored-plan fidelity, and pre-effect drift rejection.

Acceptance criteria for resolution:

- The eligible request placement override wins over the conflicting Profile placement override in the persisted plan.
- An unknown request placement target rejects with `PMADP121` before runtime effects.
- A required parameter supplied through `RunRequest.parameter_overrides` validates and executes the existing portable filter, producing `[2, 3]`.
- Equivalent supported class/definition planning inputs resolve consistently; no override widens authorization, qualification, or native-body eligibility.
- Existing FINAL-004 selection/default/stored/concurrency contracts and the binding remediation continue passing.

Verification artifact: `tests/runtime/test_sol_0_53_effective_request.py`.

Verification status: EXPECTED BLOCKER VERIFICATION — all three fail for the identified behavior; artifact Ruff lint/format and explicit Pyright checks pass.

**ESCALATION RECOMMENDED:** FINAL-004 has survived multiple remediation attempts. Use a stronger implementation model and trace effective-input resolution through public validation, graph construction, candidate restriction, and stored execution. The approved architecture already specifies precedence; no architectural redesign or unrelated remediation is requested.

## Acceptance criteria

| AC | Status | Evidence |
|---|---|---|
| AC-001 | VERIFIED | Explicit compatibility and no-adaptive sentinels; exact-HEAD CI. |
| AC-002 | VERIFIED | Qualified public class/definition/CLI/stored execution and support rejection campaign. |
| AC-003 | PARTIALLY SATISFIED | Existing serialization/variant tests pass; effective request precedence fails. |
| AC-004 | VERIFIED | Whole-DAG admission and zero-effect controls. |
| AC-005 | VERIFIED | Exact authorization/version/binding/capability drift controls; fresh binding drift probe. |
| AC-006 | VERIFIED | Metadata-only analysis, dispatch identity, unsupported version/kind controls. |
| AC-007 | NOT SATISFIED | Scope/default controls pass; three effective-request blocker contracts fail. |
| AC-008 | VERIFIED | Stored dependency/results-before-ready execution controls. |
| AC-009 | VERIFIED | Captured concurrency and policy boundary controls. |
| AC-010 | VERIFIED | Real-backend typed/empty/null preparation and native invocation sentinels. |
| AC-011 | VERIFIED | Both real Arrow directions and distinct port routing. |
| AC-012 | VERIFIED | Finite collection and unsupported policy controls. |
| AC-013 | VERIFIED | Validation/schema/freshness barriers and pre-publication failures. |
| AC-014 | VERIFIED | Owned checkpoint/reuse/retention and failure controls. |
| AC-015 | VERIFIED | Fused failure prefix, retry and timeout contracts. |
| AC-016 | VERIFIED | Dependency failure, independent branches and terminal logical outcomes. |
| AC-017 | VERIFIED | Cancellation/deadline/native drain/late fencing controls. |
| AC-018 | VERIFIED | Sole publication authority and explicit writer compatibility. |
| AC-019 | VERIFIED | Unknown/known receipt, ack loss, timeout and cleanup/report failure controls. |
| AC-020 | VERIFIED | Physical/logical report provenance and accounting contracts. |
| AC-021 | VERIFIED | Namespaced metrics, migration and recursive privacy controls. |
| AC-022 | VERIFIED | Unqualified consumer rejection and explicit compatibility controls. |
| AC-023 | VERIFIED | Concurrent isolation, shared lifetime and cleanup obligations. |
| AC-024 | VERIFIED | Fresh 127/127 campaign/evidence verifier; Experimental docs; exact-HEAD CI packaging/runtime matrix. |

## Previous blockers

| Finding | Status | Verification |
|---|---|---|
| FINAL-001 | VERIFIED FIXED | Whole-DAG pins/admission controls and fresh source/sink binding drift probe. |
| FINAL-002 | VERIFIED FIXED | Exact required topology/port/support campaign. |
| FINAL-003 | VERIFIED FIXED | Handoff, collection, materialization/reuse and retention contracts. |
| FINAL-004 | PARTIALLY FIXED | Binding control passes; new parameter/implementation request contracts fail. |
| FINAL-005 | VERIFIED FIXED | Publication known/unknown outcome and explicit compatibility controls. |
| FINAL-006 | VERIFIED FIXED | Concurrent logical artifact isolation controls. |
| FINAL-007 | VERIFIED FIXED | Member/run deadlines, lifecycle drain, fencing and cleanup contracts. |
| FINAL-008 | VERIFIED FIXED | Fresh non-writing evidence/source-hash gate and tamper controls. |
| FINAL-009 | VERIFIED FIXED | Semantic stage serialization/privacy contracts. |
| SOL-010 | VERIFIED FIXED | Fresh documentation consistency and strict build. |
| SOL-011 | VERIFIED FIXED | Terminal member accounting, downstream and independent branch contracts. |

## Fresh quality gates

| Gate | Executed | Result |
|---|---|---|
| `check_adaptive_0_53.py`, default non-writing | Yes | PASS — 127/127; no qualification skips; current committed source hash accepted. |
| New protected effective-request tests | Yes | EXPECTED BLOCKER VERIFICATION — 3 failures. |
| Configured core pytest selection | Yes | EXPECTED BLOCKER VERIFICATION — 3 failed, 1858 passed, 5 skipped, 407 deselected in 161.80s; all failures are the new FINAL-004 tests. |
| Ruff lint and format | Yes | PASS — 948 files formatting check; full lint passes. |
| Configured Pyright + explicit new artifact Pyright | Yes | PASS — zero errors/warnings. |
| `check_adaptive_0_52.py` | Yes | PASS — 10 artifacts, 18 criteria. |
| `check_stable_foundation.py` | Yes | PASS — 21 tests. |
| Surface inventory, diagnostics, protocol freeze, plugin manifests, security matrix, agent guidance | Yes | PASS. |
| `check_docs.py` | Yes | PASS — internal anchors, CLI/API coverage, runnable companions and consistency; external URLs inventoried, not fetched. |
| Strict docs build to `/tmp/sol053-637a-review-docs` | Yes | PASS. |
| `check_release.py` | Yes | PASS — existing 0.52.1 metadata checks. |
| `git diff --check` | Yes | PASS. |
| Exact-HEAD GitHub CI run 34883818078 | Inspected | PASS — all 37 jobs, before the new verification artifact. |
| Fresh isolated wheel build/import | No | Not independently rerun locally; exact-HEAD CI provides packaging evidence. |

CI: https://github.com/eddiethedean/etlantic/actions/runs/34883818078

Core command: `uv run --no-sync pytest -q -m 'not medallantic and not polars and not pandas and not sql and not spark and not real_pyspark and not airflow and not prefect and not keyring and not sqlmodel and not datafusion'`. Output captured outside the repository at `/tmp/sol053-637a-core-review.log`. Targeted blocker output is `/tmp/sol053-637a-effective-request-review.log`. The core selection follows the existing CI selection; real backend qualification is independently exercised by the 0.53 campaign.

The existing 127-case campaign does not include the new effective-request artifact. This explains how its green result and green pre-artifact CI can coexist with the demonstrated contract violation. No discovery exclusion or quality gate was weakened in this review.

Additional fresh diagnostic evidence outside the repository: registered JSON source/sink overrides resolve identically through four public planning variants; the serialized plan executes through LocalScheduler and writes the expected JSON; post-planning descriptor replacement rejects with `PMADP501` and leaves the sink unchanged.

## New blockers

None with a new root cause or ID. FINAL-004 remains the sole open blocker.

## Follow-ups

| Finding | Severity | GitHub |
|---|---|---|
| SOL-012 — Pre-existing Medallantic migration fingerprint golden discrepancies | Low | EXISTING ISSUE [#145](https://github.com/eddiethedean/etlantic/issues/145), confirmed OPEN. Outside the approved boundary. |
| Deadline verification sensitivity to compiler startup timing | Low | EXISTING ISSUE [#146](https://github.com/eddiethedean/etlantic/issues/146), confirmed OPEN. Current qualified campaign passes. |

No new follow-up findings. No duplicate issues created. Neither follow-up enters blocker remediation.

## Observations

None requiring action.

## Convergence

Binding-specific FINAL-004 behavior is now verified fixed, but the root effective-request boundary remains incomplete. One previously open blocker is partially fixed; one blocker remains; zero new independent blockers or substantive regressions attributable to the binding patch were found; zero new follow-ups. The next implementation work is bounded to FINAL-004. The loop has not yet converged to a passing contract.

## Verdict

NEEDS FIXES
