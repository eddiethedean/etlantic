# Sol production re-review — phase 0.53

Reviewed production: `a0d134780be439be86c00f812e4b49caa596e33c`.
Verdict: **NEEDS FIXES**.

## Contract, scope and independence

Authority remains [IMPLEMENTATION_PLAN_0_53.md](../../../docs/11_DEVELOPMENT/IMPLEMENTATION_PLAN_0_53.md),
its REQUIRED BEHAVIOR, AC-001–AC-024, verification matrix and explicit non-scope.
Reconstructed the contract from that plan, original/repeated Sol reviews,
admission/boundary and CI repair reports, both recent Luna resolution reports,
actual implementation, public dispatch, relevant tests, documentation, packaging
and configured CI. Implementation claims and the prior green CI are evidence,
not approval. The stable FINAL IDs are retained.

This is Experimental, fixture-qualified static local `/2` execution: Local,
Polars, Pandas and both directional Arrow families; exact named topology/port
signatures; complete live admission; stored dependency scheduling; actual
boundary operations; publication receipts; lifecycle; privacy; explicit `/1`
compatibility. The previously resolved restriction to qualified unfused
realizations remains: fused signatures reject rather than inherit qualification.
SQL/Spark adaptive execution, durable/control-plane acceptance, broader DAGs,
new optimizers, producer-skipping cache behavior and unrelated repair remain
outside this review.

Inspected the remediation diff from `c9d1986a`, the full change boundary relative
to `v0.52.1`, and the native invocation, dataframe helper, host registration,
physical scheduler, cancellation/cleanup/report and publication paths. No
substantive unrelated scope expansion, dependency change, public wire-format
change or persistence migration was established. Python remains >=3.11;
qualification is Linux/macOS/Windows × Python 3.11/3.12/3.13 with core/plugins
0.52.1, Polars 1.42.1, Pandas 2.3.3 and PyArrow 25.0.0.

This review changes only one protected verification case and this report.
Production, all previous assertions/fixtures, configuration, package metadata,
documentation and committed qualification evidence are unchanged.

## Acceptance criteria

Before adding verification, the original non-writing campaign executed/passed
105 cases, including all 37 previous protected Sol cases and five native
implementation cases. All nine exact-head CI bundles were independently
downloaded and their source, scenarios/JUnit and output digests validated.
Evidence below also includes inspection of the relevant production paths.

| AC | Status | Evidence / remaining gap |
|---|---|---|
| AC-001 | VERIFIED | Protected explicit host-Future compiler test passes; the helper directly awaits explicit compilers on their host loop. Core compatibility tests and separate `/1` dispatch remain passing. |
| AC-002 | VERIFIED | Five-family differentials, exact diamond/fanout/dual-port/partial-chain qualification and public dispatch/support restrictions pass; no wider target or topology authority is added. |
| AC-003 | VERIFIED | Effective/default request, stored portable round trip, marker/envelope tamper and historical wire controls pass; executable serialization is unchanged by this remediation. |
| AC-004 | VERIFIED | Last-dependency/support-analysis, unauthorized storage and incomplete-operation controls pass; live admission still precedes session/effects. |
| AC-005 | VERIFIED | Run-local pins and exact authorization/identity/version/capability/evidence/binding/contract checks remain; replacement rejection controls pass. |
| AC-006 | VERIFIED | Metadata-only analysis, public result identity/routing and executor lifecycle checks pass; explicit async compiler compatibility is restored. |
| AC-007 | VERIFIED | Stored request/scope comparisons, partial selection and stored implementation execution pass; no runtime re-slice or native-body substitution. |
| AC-008 | VERIFIED | Dependency/readiness, transitive no-start, branch and routed-result checks pass; no new logical ready loop or runtime insertion. Expired member output is separately FINAL-007/AC-017. |
| AC-009 | VERIFIED | Numeric boundaries, Profile/request concurrency precedence and bounded physical scheduling controls pass. |
| AC-010 | VERIFIED | Real five-family typed-empty/nullable portable differentials and sink preparation pass; unqualified fusion remains rejected. |
| AC-011 | VERIFIED | Both real Arrow directions and distinct port routes pass; conversion remains in the stored transfer unit. |
| AC-012 | VERIFIED | Actual finite collection/bound success and failure controls pass; unsupported distributed policies reject. |
| AC-013 | VERIFIED | Real Local/Polars/Pandas passing/failing validation barriers and publication suppression pass; schema inspection still executes, but its deadline is the FINAL-007 lifecycle gap below. |
| AC-014 | VERIFIED | Real checkpoint/reuse controls and all four retention tests pass; finite timestamp validation remains at the shared read boundary. |
| AC-015 | PARTIALLY SATISFIED | Unsafe retry rejection and native member timeout/no-retry controls pass. Post-compile schema work can exceed the hard member deadline yet produce success. FINAL-007. |
| AC-016 | VERIFIED | Transitive failure and independent branch outcomes pass; selected nodes have terminal logical reports. |
| AC-017 | PARTIALLY SATISFIED | Native member/run/external cancellation ownership and awaited cancel/cleanup pass. The result fence precedes schema work; a late post-compile result still registers/publishes. FINAL-007. |
| AC-018 | VERIFIED | Actual memory/file receipts, atomic JSON/CSV overwrite and admitted-provider failure controls pass; only publication commits. The late result reaching publication is FINAL-007, not a new receipt defect. |
| AC-019 | VERIFIED | Ack loss, post-commit deadline and explicit writer-timeout controls pass; unknown/publication reconciliation IDs remain retained. |
| AC-020 | VERIFIED | Existing logical/trace/summary projection and boundary attribution controls pass. Incorrect deadline success is the existing lifecycle root, not a new trace finding. |
| AC-021 | VERIFIED | Recursive row/native-ref/receipt privacy, namespaced writers and core reader-migration controls pass; owner metadata contains identifiers rather than buffers. |
| AC-022 | VERIFIED | Closed unsupported-consumer/runtime restrictions and existing explicit worker/compiler/control-plane compatibility pass; no durable adaptive qualification claim. |
| AC-023 | VERIFIED | Shared final-consumer cleanup, concurrent artifact isolation and actual native unit/member/attempt owner controls pass. The worker closure retains compiler/input buffers; queued cancelled work cannot start afterward. |
| AC-024 | PARTIALLY SATISFIED | Original 105 cases pass locally and across nine independently verified CI bundles; docs/wheel/static gates pass. Expanded required-behavior campaign has one expected FINAL-007 failure and cannot establish the complete release contract. |

## Previous blockers

| Finding | Status | Verification |
|---|---|---|
| FINAL-001 | VERIFIED FIXED | Qualified all-unit analysis, unauthorized storage and admitted pin replacement controls pass; live admission/pin dispatch inspected. |
| FINAL-002 | VERIFIED FIXED | Exact required branch, partial-chain and both-direction distinct-port cases pass; independent packaged support remains closed. |
| FINAL-003 | VERIFIED FIXED | Actual boundary/routing/checkpoint/reuse tests and four retention controls pass; no relevant remediation change. |
| FINAL-004 | VERIFIED FIXED | Default/effective request, stored portable execution, scope, numeric policies and Profile precedence controls pass. |
| FINAL-005 | VERIFIED FIXED | Definite failure, ack loss, post-commit deadline, atomic file receipt and explicit writer-timeout controls pass. |
| FINAL-006 | VERIFIED FIXED | Same-runtime concurrent artifact isolation remains passing; not reopened. |
| FINAL-007 | PARTIALLY FIXED | Previous member/run ownership and explicit host-resource checks pass. New post-compile schema deadline/fencing test fails for late success/publication. |
| FINAL-008 | VERIFIED FIXED | Non-writing gate and tampered/fabricated/skipped-proof controls pass before additions; nine source/output-bound CI bundles verified. Expanded campaign correctly fails on the new requirement check. |
| FINAL-009 | VERIFIED FIXED | Recursive sensitive-row/native-ref/unknown-receipt projections remain passing. |
| SOL-010 | VERIFIED FIXED | Fresh documentation consistency and strict build pass; Experimental claims remain truthful. |

## Remaining blocker

### FINAL-007 — Post-compile schema work can bypass the member deadline and publish late output

Severity: **High**.
Disposition: **BLOCKER**.
Related AC: **AC-015, AC-017**; consequential **AC-024**.

Location:

- `src/etlantic/runtime/dataframe_exec.py:455–462`, final helper deadline fence.
- `src/etlantic/runtime/orchestrator.py:3129–3155`, `_run_node_once` schema work and output registration.
- `src/etlantic/runtime/orchestrator.py:4570`, `_observe_schema`; calls the synchronous `plugin.inspect_schema` through `_observe_records_schema`.
- `_execute_node` wraps the complete member in `anyio.fail_after`, then records success without a final effective-deadline check.

Problem: The new check covers compiler execution and dataframe normalization/
validation, but it runs before `_observe_schema`. That async method performs
synchronous schema inspection/history/drift work without yielding. If this work
crosses the member deadline, the event loop cannot deliver its timeout callback.
The host registers outputs and exits the member cancel scope successfully before
that callback runs. A helper-local checkpoint is therefore not a complete
member result/success fence.

Evidence: Execute the real qualified Polars chain with `step_seconds=0.1`.
Preserve the original admitted `inspect_schema` implementation and its result,
injecting 0.3 seconds of latency only for `identity="observed:first"`. Compiler
execution and validation finish before the helper check; the subsequent schema
operation is entered. The manual exercise observes the first member taking
approximately 0.305 seconds, all members/run reporting `succeeded`, an available
`first.result` artifact and one sink effect. The protected automated test fails
on `succeeded` versus required `timed_out`, not on admission, imports or fixtures.
No native worker/resource is left pending by the injected schema operation.

Relationship to current change: This is the already-open FINAL-007 hard-deadline/
late-result root in the `/2` host. The remediation added a partial fence and its
own passing slow-output-validation case; it did not cover the later production
schema path. The native owner and explicit compatibility defects from the last
review are genuinely resolved. No new finding ID or explicit `/1` redesign is
requested.

Why it matters / why this blocks the current change: The approved hard member
deadline and no-late-registration/publication guarantees are violated by the
changed functionality. A timed-out adaptive member can instead be entirely
successful and commit downstream. This is an in-scope correctness/lifecycle
failure under blocker tests 1, 4 and 6; a green compiler-only or pre-schema
validation test cannot justify releasing it.

Required behavior: Enforce cancellation/effective member deadline across the
complete admitted member before exposing successful outputs and terminal
success, including schema work after compilation. Expired outputs must not
become available or release dependent publication. Attribute timeout to the
member, suppress its dependents and do not retry timeout. Preserve existing
native drain/abandonment ownership/buffer lifetime, explicit host-loop compiler
compatibility, cooperative cleanup, receipts and concurrent isolation. Do not
special-case this schema identity, input or delay; no particular internal guard,
threading or staging design is prescribed.

Acceptance criteria for resolution: The new test passes with one timed-out
attempt, skipped second member, no available `first.result`, zero sink effect and
non-successful run. Every previous protected case and native implementation
case remains passing; complete five-family qualification and relevant explicit
runtime/quality gates pass. Source-bound evidence must be regenerated only after
the required behavior passes its unchanged verification process.

Verification artifact:
`tests/runtime/test_sol_0_53_contract_rereview.py::test_final_007_post_compile_schema_deadline_fences_registration`.

Verification status: **FAIL — EXPECTED BLOCKER VERIFICATION**. Targeted run:
one expected failure, 17 deselected. Expanded campaign: 105 passed, one expected
failure, 106 executed, no skipped required case and `source_changed=false`.
All 37 previous protected cases and five implementation cases pass.

**ESCALATION RECOMMENDED:** FINAL-007 has survived several fixes at individual
await/helper boundaries. Use focused architectural review of where the complete
adaptive attempt commits output visibility and success, or a stronger
implementation model for that bounded invariant. Native ownership and explicit
compatibility do not need to be redesigned; no runtime-wide cleanup is requested.

## Quality gates and verification audit

Fresh local execution: Darwin arm64, Python 3.11.15, exact qualified backend
versions. Repository was clean at start. Pre-addition gates are explicitly
identified and are not claimed to qualify the expanded verification tree.

| Gate | Executed | Result / classification |
|---|---|---|
| Original non-writing 0.53 campaign | Locally, before addition | PASS — 105/105 executed/pass; committed proof matches; source_changed=false. |
| Configured core marker suite | Locally, before addition | PASS — 1,851 passed, 5 existing skips, 392 deselected, 48 warnings; 182.23 seconds. Includes historical regeneration verification. |
| Historical 0.52 non-writing verifier | Locally, before addition | PASS — 10 artifacts, 18 criteria; no historical claim rewritten. |
| Ruff check / format | Locally, before and after addition | PASS — 947 Python files formatted; previous protected assertions unchanged. |
| Configured Pyright | Locally, before and after addition | PASS — zero errors/warnings. |
| Documentation consistency | Locally | PASS — existing ignored external-URL report only. |
| Official strict docs build | Locally, temporary site directory | PASS — 26.00 seconds. |
| Core wheel build / isolated import | Locally, isolated temporary environment | PASS — core, physical protocol and native helper import with Polars/Pandas/PyArrow absent. |
| New protected FINAL-007 test | Locally | EXPECTED BLOCKER VERIFICATION — late member success rather than timeout. |
| Expanded campaign, temporary output | Locally, after addition | 105 passed / 1 EXPECTED BLOCKER VERIFICATION failure; 106 executed, source_changed=false; protected subset 37 passed / 1 failed. |
| Exact-head GitHub CI | Independently retrieved | PASS — all 37 jobs, [run 34794718690](https://github.com/eddiethedean/etlantic/actions/runs/34794718690), exact head a0d13478. Includes optional backend/compiler, wheel, docs, security/static and configured compatibility checks; predates the new test. |
| Nine required CI proof bundles | Independently downloaded/validated | 105/105 pass in each OS/Python environment; source/JUnit/scenario agreement and stdout/stderr/JUnit SHA-256 verified. Not represented as local cross-OS execution or proof of the new test. |
| Optional Pyright on entire protected file + native helper | Locally, outside configured gate | Eight pre-existing fixture/import typing diagnostics; identical eight errors reproduced from the unmodified HEAD file in a temporary copy. No new diagnostics; configured gate remains green. |

Pre-addition source fingerprint:
`sha256:16a77dcd863801ddee082063d2207398adb34419c2d2df29c8490fee2354c09e`.
Expanded evidence: `/tmp/sol053-a0-expanded-review-proof/qualification.json`,
source `sha256:1fd511f853b1331c0c0e31e292971bcd491d7f3f03ea241b475a01e75f3ae6b8`.
Committed passing evidence/support records were not regenerated to conceal the
failure. Their now-old source binding is an expected review-input change,
not a new verifier malfunction or separate production blocker.

The green suite was challenged with a technically concrete path: previous
latency tests stop inside native execution or dataframe validation, both before
the new check. Schema inspection follows it in the actual host. Keeping the
real schema result demonstrates that the misplaced fence, rather than compiler
output correctness, permits late publication. One additional case establishes
this gap; equivalent permutations are not added.

## Follow-ups and observations

New substantive FOLLOW-UP findings: **None**. Existing plan tracking #83/#86
remains outside remediation. No duplicate GitHub issue is created for this
existing blocker.

Observation (Low, non-blocking): Optional static checking of the entire protected
test module reports the same eight existing fixture/import typing diagnostics
at HEAD and after addition. This is outside the configured gate and introduces
no new test/production type error; no remediation or issue is required here.

## Convergence and handoff

- Nine historical blocker IDs remain VERIFIED FIXED.
- FINAL-007's run/external native owner and explicit async compatibility gaps
  are newly verified resolved; its post-compile late-result boundary remains.
- Blockers remaining: **one — FINAL-007**.
- New blocker IDs: **zero**. No newly introduced remediation regression was
  independently established; this is incomplete resolution of the same root.
- New follow-ups: **zero**.
- The loop is bounded and the resolved parts are preserved, but the final
  output/success boundary still needs one coherent invariant-based fix.

Only FINAL-007 enters Luna/Terra remediation. Preserve all protected verification
and fix the complete member deadline/visibility invariant. Do not implement
observations, unrelated follow-ups or explicit-runtime redesign. Obtain a normal
Sol PASS before a final release check.

**NEEDS FIXES**
