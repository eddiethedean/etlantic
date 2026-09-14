# Sol Production Re-review — Phase 0.53

Reviewed HEAD: `59946da45e1c9196eb6db512bd7a1cd2c0acf208`.

Verdict: **NEEDS FIXES**. The three previously failing effective adaptive
request cases are fixed, but the shared implementation resolver change
regresses explicit `/1` native request overrides. FINAL-004 remains the sole
open blocker; its stable ID is retained for this regression in the same
effective-override remediation path. This review changes only a new protected
verification artifact and this report. Production, existing tests, configuration,
and committed evidence are unchanged. Both pre-existing untracked review notes
are preserved.

## Contract and scope

Authority: `docs/11_DEVELOPMENT/IMPLEMENTATION_PLAN_0_53.md`, its 24 ACs and
verification matrix, and ADR-025. The scope remains Experimental,
fixture-qualified local static-batch physical-DAG execution across Local,
Polars, Pandas, and both qualified Arrow directions. Effective request inputs
must precede adaptive validation and candidate construction; stored descriptors
remain adaptive runtime authority. Explicit `/1` bytes, runtime and public
request behavior must remain compatible. Durable/remote execution, arbitrary
topologies, additional backend qualification and repository-wide cleanup remain
excluded.

The new placement context merge and immutable parameter graph overlay are
within scope. No new dependency or gate bypass was introduced. The shared
`LocalOrchestrator._resolve_implementation` change applies outside adaptive
execution and has a concrete compatibility consequence.

## FINAL-004 — Effective override remediation ignores explicit native requests

Severity: High

Disposition: BLOCKER

Related AC: AC-001; preserves the original FINAL-004 relationship to
AC-003/AC-007, whose demonstrated adaptive cases now pass.

Location: `src/etlantic/runtime/orchestrator.py:3973`,
`LocalOrchestrator._resolve_implementation`.

Problem: The remediation removes the request implementation override from a
shared resolver, unconditionally selecting `descriptor.engine`. This is also
the explicit native step execution path. A valid explicit request selecting a
different registered native implementation is silently ignored.

Evidence:

- The protected test has native `local` and `null` implementations producing
  IDs 1 and 2 respectively. The default explicit Profile plans `local` and the
  public `arun_pipeline` request overrides the step to `null`.
- HEAD returns a successful report but publishes `[1]` instead of `[2]`.
- Targeted verification fails with `assert [1] == [2]`, **1 failed in 1.16s**.
- In an isolated diagnostic process, restoring only the exact parent revision
  (`637aebb8`) resolver makes the same verification pass: **1 passed in 1.10s**.
  The parent method was extracted from Git and installed in that process only;
  the repository was not modified. A separate public runtime comparison likewise
  printed `HEAD succeeded [1]` and `PARENT RESOLVER succeeded [2]`.
- The diff removes
  `self.request.implementation_overrides.get(node.name)` from the resolver.
  Explicit `arun_pipeline` does not pass the request to the explicit planner,
  so no other path now applies this established native override.

Relationship to current change: Introduced by `59946da4` while remediating
FINAL-004. This is a regression in that same override path, not unrelated
repository debt or a new architectural requirement.

Why it matters: The run can succeed while executing and publishing output from
the wrong user-selected implementation.

Why this blocks the current change: AC-001 explicitly preserves existing `/1`
runtime/plugin outcomes and behavior. This change silently changes the public
explicit native request contract and produces different output. It therefore
fails the regression and required-compatibility blocker tests even though the
adaptive override reproducers and existing CI are green.

Required behavior: Preserve explicit native request implementation override
precedence. Adaptive execution must continue using admitted, stored placement
and compiler descriptors; do not reintroduce target-ID interpretation or live
substitution in the physical path. Bound the repair to the schema/mode distinction
in the existing resolver or an equivalent existing execution boundary.

Acceptance criteria for resolution:

1. The new public explicit native override test publishes ID 2 and succeeds.
2. All three original effective-request tests still pass, including request
   placement precedence, unknown target rejection and required parameters.
3. Stored adaptive authority, existing explicit behavior and relevant core/
   physical qualification gates remain intact.
4. Protected verification assertions and discovery remain unchanged.

Verification artifact:
`tests/runtime/test_sol_0_53_explicit_override.py::test_final_004_explicit_native_request_override_still_selects_implementation`.

Verification status: **EXPECTED BLOCKER VERIFICATION** — fails for the expected
wrong-output reason. Artifact Ruff lint/format and explicit Pyright pass.

The repeated FINAL-004 history warrants **ESCALATION RECOMMENDED** for
implementation reasoning across explicit and adaptive execution boundaries.
The current failure mechanism is identified; no specification change or major
architectural redesign is required.

## Acceptance criteria

| AC | Status | Evidence |
|---|---|---|
| AC-001 | REGRESSED | Existing compatibility/core controls pass; fresh explicit native override publishes the wrong implementation output. FINAL-004. |
| AC-002 | VERIFIED | Public entry/stored scheduler controls and five-family real qualification pass; unsupported signatures reject. |
| AC-003 | VERIFIED | Three effective-request tests, definition placement variant test, stored descriptors, historical wire and envelope tamper controls pass. |
| AC-004 | VERIFIED | Whole-DAG/last-dependency zero-effect admission controls pass. |
| AC-005 | VERIFIED | Exact authorization/version/binding/capability drift and post-admission pin controls pass. |
| AC-006 | VERIFIED | Metadata-only analysis, exact dispatch/result identity and unsupported protocol/kind controls pass. |
| AC-007 | VERIFIED | Adaptive request parameters and target precedence, unknown target rejection, native exclusion, scope/default/stored drift controls pass. Explicit compatibility regression is AC-001. |
| AC-008 | VERIFIED | Stored dependency/results-before-ready and no downstream start controls pass. |
| AC-009 | VERIFIED | Captured bounded concurrency and numeric policy boundaries pass. |
| AC-010 | VERIFIED | Real target preparation, typed-empty/null differentials and native invocation sentinels pass. |
| AC-011 | VERIFIED | Both real Arrow directions and distinct port route/conversion controls pass. |
| AC-012 | VERIFIED | Real finite collection/bounds and unsupported-policy controls pass. |
| AC-013 | VERIFIED | Validation/schema/freshness and pre-publication failure/deadline barriers pass. |
| AC-014 | VERIFIED | Owned checkpoints, reuse/retention, malformed state and partial-write failure controls pass. |
| AC-015 | VERIFIED | Fused failure prefix, attempts, safe retry and member timeout controls pass. |
| AC-016 | VERIFIED | Returned failure branches retain terminal logical reports; failed dependents and independent publication controls pass. |
| AC-017 | VERIFIED | Native drain/abandon, member/run/boundary deadlines, late fencing and cleanup controls pass. |
| AC-018 | VERIFIED | Sole publication, memory/JSON/CSV receipts, destination locking and explicit writer compatibility controls pass. |
| AC-019 | VERIFIED | Known/unknown commit receipts, acknowledgement loss, timeout and retained obligations controls pass. |
| AC-020 | VERIFIED | Physical/logical provenance, attribution and semantic accounting controls pass. |
| AC-021 | VERIFIED | Namespaced writer/migration and recursive semantic failure/receipt privacy controls pass. |
| AC-022 | VERIFIED | Unsupported consumer/durable/dynamic rejection controls and Experimental documentation pass. |
| AC-023 | VERIFIED | Concurrent run isolation, shared/owned/borrowed lifetime and cleanup obligations pass. |
| AC-024 | VERIFIED | Fresh non-writing 128/128 real campaign, current evidence, docs/core build and exact-HEAD 37-job CI pass. The new explicit override test is separately failing. |

## Previous blockers

| Finding | Status | Verification |
|---|---|---|
| FINAL-001 | VERIFIED FIXED | Whole-DAG admission, immutable executor/binding pins, storage denial and replacement controls pass. |
| FINAL-002 | VERIFIED FIXED | Exact chain/diamond/fanout and directional multi-port topology/support controls pass. |
| FINAL-003 | VERIFIED FIXED | Real handoff, finite collection, checkpoint/reuse and retention controls pass. |
| FINAL-004 | REGRESSED | Original 3/3 adaptive effective-input contracts pass; new explicit native compatibility contract fails. |
| FINAL-005 | VERIFIED FIXED | Publication failure, known/unknown outcome, acknowledgement loss and explicit writer controls pass. |
| FINAL-006 | VERIFIED FIXED | Concurrent same-runtime artifact isolation controls pass. |
| FINAL-007 | VERIFIED FIXED | Member/run/boundary deadline, native ownership/drain and fencing controls pass. |
| FINAL-008 | VERIFIED FIXED | Non-writing current-source evidence and fabricated/skipped/tampered proof controls pass. |
| FINAL-009 | VERIFIED FIXED | Semantic failure-stage and recursive protocol/receipt privacy controls pass. |
| SOL-010 | VERIFIED FIXED | Documentation consistency and strict temporary-directory build pass. |
| SOL-011 | VERIFIED FIXED | Failed returned-outcome branch retains all terminal logical reports and truthful accounting. |

## Quality gates

| Gate | Executed | Result |
|---|---|---|
| Protected effective-request + previous Sol + adaptive execution suites | Yes | PASS — 56 tests, one existing namespace warning. |
| Default non-writing `check_adaptive_0_53.py` | Yes | PASS — 128 executed/passed, no skips, `source_changed=false`; committed source hash accepted. |
| Configured core marker suite | Yes | PASS — 1862 passed, 5 skipped, 407 deselected, 48 warnings, 164.43s; collected before new artifact was created. |
| New explicit override verification | Yes | EXPECTED BLOCKER VERIFICATION — 1 failure, wrong implementation output. |
| Full Ruff lint/format + configured Pyright | Yes | PASS — 948 pre-artifact files formatted; zero type errors/warnings. |
| New artifact Ruff lint/format + explicit Pyright | Yes | PASS. |
| `check_adaptive_0_52.py` | Yes | PASS — 10 artifacts, 18 criteria. |
| Stable foundation | Yes | PASS — 21 tests. |
| Surface, diagnostics, protocol freeze, manifests, security matrix, agent guidance | Yes | PASS. |
| `check_docs.py` | Yes | PASS; external URLs inventoried, not fetched. |
| Strict docs build | Yes | PASS — output `/tmp/sol053-59946-docs`. |
| `check_release.py` | Yes | PASS — existing 0.52.1 metadata. |
| Core sdist and wheel build | Yes | PASS — output `/tmp/sol053-59946-build`. |
| Isolated optional-free wheel import / broader optional and OS matrix | Inspected CI | PASS evidence from exact-HEAD CI; not independently rerun locally. |
| Exact-HEAD GitHub CI run `34889409463` | Inspected | PASS — all 37 jobs at `59946da4`, before this new protected test. |
| `git diff --check` | Yes | PASS. |

Fresh environment: macOS arm64, Python 3.11.15, core 0.52.1, Polars 1.42.1,
Pandas 2.3.3, PyArrow 25.0.0. Qualification source:
`sha256:8af25289674196afc3d4634aef17c1b4325b602085ed8760ff2c7c2866d40267`.

Core command:
`uv run --no-sync pytest -q -m 'not medallantic and not polars and not pandas and not sql and not spark and not real_pyspark and not airflow and not prefect and not keyring and not sqlmodel and not datafusion'`.

Logs are outside the repository at `/tmp/sol053-59946-{core,protected,qualification,new-blocker,static,gates,historical,build,docs}.log`.

CI: https://github.com/eddiethedean/etlantic/actions/runs/34889409463

## New blockers

No new finding ID or independent root cause. The explicit regression caused by
FINAL-004 remediation keeps that finding open.

## Follow-ups

| Finding | Severity | GitHub |
|---|---|---|
| SOL-012 — Pre-existing Medallantic migration fingerprint golden discrepancies | Low | EXISTING ISSUE #145, confirmed OPEN. |
| Deadline verification sensitivity to compiler startup timing | Low | EXISTING ISSUE #146, confirmed OPEN; current campaign passes. |

No new follow-ups or duplicate issues. These do not enter remediation.

## Observations

None requiring action. Green pre-artifact CI and the green qualification
campaign lacked explicit native request override coverage; the new protected
test fills that concrete gap without altering existing tests or gate discovery.

## Convergence

- The original three FINAL-004 adaptive failures are resolved.
- Ten other previous blocker findings remain verified fixed.
- One blocker remains: FINAL-004's explicit compatibility regression.
- One regression attributable to remediation; no unrelated scope expansion.
- Zero new follow-ups.
- The loop is narrowing, but is not complete. Remediation must preserve both
  public explicit request semantics and stored adaptive authority.

**NEEDS FIXES**
