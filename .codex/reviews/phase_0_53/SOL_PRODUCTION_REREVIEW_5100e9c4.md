# Sol Production Re-review — Phase 0.53

Reviewed HEAD: `5100e9c4a4fdfcb1d5304e1112590d02b881910e`.

Verdict: **NEEDS FIXES**. Normal explicit native request overrides now work,
and the original adaptive parameter/placement contracts remain fixed. However,
the same mode distinction regresses an independently generated `/1` fallback:
its original adaptive request target ID is interpreted as a native engine.
FINAL-004 remains the sole open finding. This review adds only a protected
verification artifact and this report. Production, existing tests, configuration,
and committed qualification evidence are unchanged. The three existing local
untracked review notes are preserved.

## Contract and scope integrity

Authority: `docs/11_DEVELOPMENT/IMPLEMENTATION_PLAN_0_53.md`, its public
entry/request contract, ACs and verification matrix, and ADR-025. The scope
remains Experimental, fixture-qualified local static-batch physical execution
across the five required families; captured inputs, exact admission and stored
dispatch authority; and explicit `/1` compatibility. Planning-time opted-in
fallback independently generates `/1` using existing explicit validation.
Stored `/2` cannot downgrade or acquire native execution authority.

This verification uses the existing permitted planning-time fallback and
existing explicit LocalScheduler surface. It adds no adaptive native
qualification, fallback after admission, arbitrary topology or new backend.
Durable/remote execution and repository-wide cleanup remain excluded.

The production repair is otherwise focused: explicit host mode restores the
parent precedence expression, while physical host mode retains descriptor
authority. LocalScheduler sets physical mode for actual `/2` execution and
leaves it false for `/1`. No dependencies, public signatures, CI gates or
discovery exclusions changed. Source-bound evidence changes are generated
revision metadata only; protected explicit regression contents are intact.

## FINAL-004 — Fallback reinterprets a resolved placement target as an engine

Severity: Medium

Disposition: BLOCKER

Related AC: AC-001. Retains FINAL-004's original effective-request association
with AC-003/AC-007; the original adaptive cases and normal explicit native case
now pass.

Location:

- `src/etlantic/runtime/orchestrator.py:3973–3975`,
  `LocalOrchestrator._resolve_implementation`.
- `src/etlantic/planning/adaptive.py:2307–2339`, existing independently
  validated explicit fallback converts profile target overrides to engine
  descriptors.

Problem: `physical_mode=False` includes both a normal explicit request and an
explicit fallback produced from an adaptive request. The repair treats every
override literal in that mode as an engine name. Fallback planning has already
resolved the adaptive literal as a placement target and recorded its `local`
engine. Execution supersedes that valid decision with the original target ID,
which is not an engine. A valid returned `/1` plan then fails its step after the
source has executed.

Evidence:

1. Existing native pipeline fixture has `local` and `null` implementations.
   The profile opts into adaptive planning, `adaptive_fallback="explicit"`,
   `portable_transform_policy="prefer"`, and one eligible target named
   `qualified` with engine `local`.
2. `RunRequest(implementation_overrides={"step": "qualified"})` is accepted
   by the public planner. It returns `PipelinePlan`, schema `/1`, a fallback
   record choosing `qualified`, and a step descriptor with engine `local`.
   Explicit validation has succeeded independently.
3. LocalScheduler receives the returned plan and the same request. HEAD tries
   engine `qualified`, logs `No implementation for engine 'qualified' ...
   available: local, null`, returns `partial`, and publishes no rows.
4. The new protected test fails at required status `succeeded`: **1 failed in
   7.45s**, expected runtime failure. An earlier run failed identically in 1.87s.
5. In an isolated diagnostic process, restoring only the exact resolver from
   parent `59946da4` makes the same test pass: **1 passed in 0.80s**. A separate
   public comparison printed `HEAD partial []` and
   `PARENT RESOLVER succeeded [1]`. Repository source was unchanged by these
   diagnostics; parent code was installed only in the diagnostic process.

Relationship to current change: Introduced by `5100e9c4` while repairing
FINAL-004. This is the third request-origin/execution transition in the same
effective-override invariant, alongside normal explicit and stored adaptive
execution. The stable finding is retained rather than creating a new ID.

Why it matters: Public planning succeeds and produces a valid explicit plan,
but execution interprets the accepted request differently and fails after
source I/O. The independently resolved native implementation never runs.

Why this blocks the current change: This change introduces a concrete `/1`
runtime regression in a permitted planning-time fallback. AC-001 requires
compatible explicit runtime outcomes. The same valid plan/request succeeds
with the parent resolver and fails solely because the repair reinterprets its
target ID. This satisfies the change-introduced regression and compatibility
blocker tests; it does not depend on widening the qualified `/2` matrix.

Required behavior: Preserve effective target-to-engine resolution when executing
an independently generated explicit fallback. Retain normal explicit native
request override precedence and exact stored/admitted adaptive descriptors.
Normalize the execution representation of effective request inputs at the
appropriate existing boundary, using request origin and fallback resolution
where needed. Avoid treating every non-physical request literal as an engine,
hard-coding the fixture target ID, or adding native `/2` eligibility.

Acceptance criteria for resolution:

- The protected fallback test executes its resolved `local` implementation,
  reports success, and publishes ID 1.
- The protected normal explicit request override still executes `null` and
  publishes ID 2.
- All original adaptive effective-request contracts still pass: request target
  precedence, unknown-target rejection, required parameters, immutable bindings,
  stored scope and captured concurrency.
- Physical execution retains exact admitted descriptor authority, and opted-in
  fallback remains planning-time independent `/1` generation.
- Relevant existing gates pass without weakening protected artifacts.

Verification artifact:
`tests/runtime/test_sol_0_53_fallback_override.py::test_final_004_fallback_preserves_resolved_request_target`.

Verification status: **EXPECTED BLOCKER VERIFICATION** — failure confirmed for
the target-as-engine mechanism; Ruff lint/format and explicit Pyright pass.

**ESCALATION RECOMMENDED:** FINAL-004 has survived repeated remediation. Trace
effective request meaning through planning, independent fallback and scheduler
dispatch. The solution needs reasoning at the request/execution boundary rather
than another binary resolver patch. The approved plan already permits independent
explicit fallback; qualification scope and public APIs remain bounded.

## Acceptance criteria

| AC | Status | Evidence |
|---|---|---|
| AC-001 | REGRESSED | Normal explicit override and compatibility/core controls pass; independently generated `/1` fallback now fails from target reinterpretation. FINAL-004. |
| AC-002 | VERIFIED | Qualified public/stored entries, five-family real differentials and unsupported signature controls pass. |
| AC-003 | VERIFIED | Original effective parameter/placement cases, definition variant, stored descriptors, historical wire and marker/envelope tamper controls pass. |
| AC-004 | VERIFIED | Whole-DAG and last-dependency zero-effect admission controls pass. |
| AC-005 | VERIFIED | Exact trust/version/binding/capability drift and immutable admission pins pass. |
| AC-006 | VERIFIED | Metadata-only analysis, protocol/kind rejection and exact result identity controls pass. |
| AC-007 | VERIFIED | Adaptive scope/default/stored drift, request precedence/required parameters, unknown targets and native exclusion pass. Fallback `/1` regression is AC-001. |
| AC-008 | VERIFIED | Stored dependency/results-before-ready and downstream no-start controls pass. |
| AC-009 | VERIFIED | Captured concurrency, precedence and numeric policy boundaries pass. |
| AC-010 | VERIFIED | Real target source/step/sink preparation, typed-empty/null differentials and zero native `/2` invocation controls pass. |
| AC-011 | VERIFIED | Both real Arrow directions, separate ports and conversion/routing controls pass. |
| AC-012 | VERIFIED | Real finite collection and bounds/unsupported-policy controls pass. |
| AC-013 | VERIFIED | Validation/schema/freshness and pre-publication deadline/failure barriers pass. |
| AC-014 | VERIFIED | Owned checkpoints, reuse/retention, malformed state and partial-write controls pass. |
| AC-015 | VERIFIED | Fused failure prefix, safe retry, attempts and member deadline controls pass. |
| AC-016 | VERIFIED | Every selected member retains a terminal report; failed dependents and independent branches behave correctly. |
| AC-017 | VERIFIED | Native drain/abandon, run/member/boundary deadlines, late fencing and cleanup controls pass. |
| AC-018 | VERIFIED | Sole publication authority, memory/file overwrite, destination locks and explicit writer compatibility pass. |
| AC-019 | VERIFIED | Known/unknown receipt, acknowledgement-loss, timeout and reconciliation obligation controls pass. |
| AC-020 | VERIFIED | Physical/logical attribution, provenance and semantic accounting controls pass. |
| AC-021 | VERIFIED | Namespaced writers/migration and recursive semantic failure/receipt privacy controls pass. |
| AC-022 | VERIFIED | Unsupported consumer/durable/dynamic rejection and Experimental documentation pass. |
| AC-023 | VERIFIED | Concurrent run isolation, shared/borrowed/owned lifetime and cleanup obligation controls pass. |
| AC-024 | VERIFIED | Fresh non-writing 128/128 campaign, current source evidence, docs/wheel imports and exact-HEAD CI pass; the new fallback verification fails separately. |

## Previous blockers

| Finding | Status | Verification |
|---|---|---|
| FINAL-001 | VERIFIED FIXED | Whole-DAG admission, immutable executor/binding pins and live replacement/storage denial controls. |
| FINAL-002 | VERIFIED FIXED | Exact chain/diamond/fanout, directional multi-port support and mismatch controls. |
| FINAL-003 | VERIFIED FIXED | Real handoff, finite collection, checkpoint/reuse and retention controls. |
| FINAL-004 | PARTIALLY FIXED | All original cases and normal explicit regression pass; new independent fallback transition fails. |
| FINAL-005 | VERIFIED FIXED | Publication failure, known/unknown outcome, ack loss and explicit writer controls. |
| FINAL-006 | VERIFIED FIXED | Concurrent default same-runtime artifact isolation. |
| FINAL-007 | VERIFIED FIXED | Member/run/boundary deadlines, native ownership/drain and late fencing. |
| FINAL-008 | VERIFIED FIXED | Fresh source-bound non-writing evidence and fabricated/skipped/tampered proof controls. |
| FINAL-009 | VERIFIED FIXED | Semantic failure-stage and recursive protocol/receipt privacy contracts. |
| SOL-010 | VERIFIED FIXED | Fresh documentation consistency and strict build. |
| SOL-011 | VERIFIED FIXED | Returned failure retains terminal logical reports, dependency outcomes and truthful counts. |

## Fresh quality gates

| Gate | Executed | Result |
|---|---|---|
| Protected explicit/effective request, previous Sol, adaptive execution suites | Yes | PASS — 57 tests, one existing namespace warning, 42.61s. |
| Configured core marker suite | Yes | PASS — 1863 passed, 5 skipped, 407 deselected, 48 warnings, 143.88s; collected before new artifact creation. |
| New protected fallback verification | Yes | EXPECTED BLOCKER VERIFICATION — 1 failed, target interpreted as engine. |
| Default non-writing `check_adaptive_0_53.py` | Yes | PASS — 128 executed/passing, no skips, `source_changed=false`. |
| `check_adaptive_0_52.py` | Yes | PASS — 10 artifacts, 18 criteria. |
| Full Ruff lint/format + configured Pyright | Yes | PASS — 949 pre-artifact files formatted; zero type errors/warnings. |
| New artifact Ruff lint/format + explicit Pyright | Yes | PASS after public `/1` type narrowing in the new verification. |
| Stable foundation | Yes | PASS — 21 tests. |
| Surface, diagnostics, protocol freeze, manifests, security matrix, agent guidance | Yes | PASS. |
| Documentation consistency and strict build | Yes | PASS — build `/tmp/sol053-5100-docs`; external URLs inventoried, not fetched. |
| Release metadata check | Yes | PASS — existing 0.52.1 metadata. |
| Core sdist/wheel and isolated optional-free imports | Yes | PASS — `/tmp/sol053-5100-build`; core/physical protocol import with Polars/Pandas absent. |
| Exact-HEAD GitHub CI `34891740218` | Inspected | PASS — all 37 jobs after unchanged retry; predates new fallback artifact. |
| `git diff --check` | Yes | PASS. |

Environment: macOS arm64, Python 3.11.15, core 0.52.1, Polars 1.42.1,
Pandas 2.3.3, PyArrow 25.0.0. Qualification source:
`sha256:361a114f4193c39a97e91f391fa65d48e43ec6589358888298c030c6db08c7ed`.

CI: https://github.com/eddiethedean/etlantic/actions/runs/34891740218

Core command:
`uv run --no-sync pytest -q -m 'not medallantic and not polars and not pandas and not sql and not spark and not real_pyspark and not airflow and not prefect and not keyring and not sqlmodel and not datafusion'`.

Logs are outside the repository at `/tmp/sol053-5100-*.log`. The green campaign
does not inventory this new fallback file; the pre-artifact CI therefore lacked
this transition. No existing assertion, discovery rule or gate was weakened.

## New blockers

No new stable finding ID or independent root cause. FINAL-004 remains open for
the fallback regression attributable to its latest remediation.

## Follow-ups

| Finding | Severity | GitHub |
|---|---|---|
| SOL-012 — Pre-existing Medallantic migration fingerprint goldens | Low | EXISTING ISSUE #145, confirmed OPEN. |
| Deadline verification sensitivity to compiler startup | Low | EXISTING ISSUE #146, confirmed OPEN. |

No new follow-ups or duplicate issues. CI's first attempt recorded a PyPI
connection reset and the existing deadline-sensitive fixture; both jobs passed
on unchanged retry. Fresh local qualification passes. Neither finding enters
FINAL-004 remediation.

## Observations

None requiring action.

## Convergence

- The original adaptive effective-input failures and normal explicit native
  request override are resolved.
- Ten other previous blocker findings remain verified fixed.
- One blocker remains: FINAL-004's independent fallback mode transition.
- One regression attributable to the latest remediation; zero new unrelated
  follow-ups or new finding IDs.
- The loop is narrowing to request meaning across the three execution origins,
  but remains incomplete. Repair that invariant at the existing execution
  boundary while preserving qualification and explicit compatibility.

**NEEDS FIXES**
