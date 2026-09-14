# Sol production re-review — phase 0.53

Reviewed implementation: `c9d1986a18865cf93ab4294b62cb6f0af79386e6`.
Verdict: **NEEDS FIXES**.

## Contract and scope

Authority remains
[IMPLEMENTATION_PLAN_0_53.md](../../../docs/11_DEVELOPMENT/IMPLEMENTATION_PLAN_0_53.md),
its REQUIRED BEHAVIOR, AC-001–AC-024, verification matrix, and explicit non-scope.
Read the original review, both prior re-reviews, admission/boundary and remaining
blocker reports, CI repair history, and the latest
[Luna resolution report](LUNA_RESOLUTION_FINAL_003_007.md). Implementation claims
and the previous green CI were evaluated as evidence, not approval.

The change is Experimental, fixture-qualified static local `/2` execution:
Local, Polars, Pandas, both directional Arrow families, closed named topology
and port signatures, whole-DAG live admission, stored physical scheduling and
boundary operations, publication receipts, lifecycle, privacy, and explicit
`/1` compatibility. Fused signatures remain unqualified and reject; this review
does not reopen that previously resolved support restriction. SQL/Spark adaptive
execution, durable/control-plane acceptance, new optimizers, producer-skipping
cache behavior, and unrelated cleanup remain outside this change.

Inspected the actual remediation diff and relevant public dispatch, shared
dataframe host, compiler protocol, adaptive admission/support, physical host,
dependency scheduler, artifact/checkpoint and cleanup/report paths. Package base
remains 0.52.1, Python >=3.11, with qualified Polars 1.42.1, Pandas 2.3.3 and
PyArrow 25.0.0. No dependency, public wire-format or database migration change is
introduced by this remediation. Source-bound evidence refreshes retain the
existing verification process.

This review modifies only the protected verification file (two additional
tests) and this report. Production, previous assertions, fixtures, configuration,
package metadata and committed qualification evidence are unchanged.

## Acceptance criteria

The existing 98-case campaign was rerun successfully before the new review
tests. All nine CI qualification bundles were independently downloaded and
checked against the reviewed source fingerprint and their output digests.
Passing tests below are supported by inspection of the relevant execution paths.

| AC | Status | Evidence / remaining gap |
|---|---|---|
| AC-001 | REGRESSED | Explicit `/1` still dispatches separately, but its shared portable helper now runs async compiler execution on a new worker event loop. A host-resource compiler that previously succeeded now fails. FINAL-007. |
| AC-002 | VERIFIED | Stored five-family differential, exact branch/dual-port/partial-chain tests and closed support/dispatch checks pass. No wider topology or backend claim is added. |
| AC-003 | VERIFIED | Default/effective request, portable stored-plan round trip, marker/envelope tamper and historical wire/core checks pass; serialization is unchanged by remediation. |
| AC-004 | VERIFIED | Protected last-dependency/support-analysis and unauthorized storage/operation rejection controls pass; admission precedes session/effects. |
| AC-005 | VERIFIED | Run-local live adapter pins and identity/version/capability/evidence checks remain; qualified analysis and replacement rejection controls pass. |
| AC-006 | VERIFIED | Public physical result identity/routing and executor lifecycle controls pass; no physical protocol change. The compiler compatibility regression is recorded under AC-001. |
| AC-007 | VERIFIED | Stored request/scope comparisons, partial selection and stored implementation execution controls pass. No runtime re-slice or native-body fallback is added. |
| AC-008 | VERIFIED | Stored dependency readiness, transitive failure no-start, branch and routed-result tests pass; registration still precedes readiness. |
| AC-009 | VERIFIED | Numeric policy, captured Profile/request concurrency precedence and bounded physical scheduling controls pass. |
| AC-010 | VERIFIED | Real five-family typed-empty/nullable portable differential and sink preparation tests pass; unqualified fusion remains rejected. |
| AC-011 | VERIFIED | Both real Arrow directions and distinct port routes pass; conversion remains inside the stored transfer unit. |
| AC-012 | VERIFIED | Actual finite collection and row-bound success/failure tests pass; no distributed collection is admitted. |
| AC-013 | VERIFIED | Real local/Polars/Pandas passing/failing validation barriers pass with affected publication suppressed on failure. |
| AC-014 | VERIFIED | Checkpoint write/reuse cases and all four retained retention cases pass. Shared read validation rejects non-boolean/non-numeric/non-finite timestamps before selecting cached rows. FINAL-003 resolved. |
| AC-015 | VERIFIED | Native member deadline now produces timeout without retry; unsafe retry admission and cooperative lifecycle controls pass. |
| AC-016 | VERIFIED | Failed-dependency and independent branch terminal outcomes remain passing. |
| AC-017 | PARTIALLY SATISFIED | Native step deadline fences late output, and awaited executor cancel/cleanup passes. Run deadline abandons the native worker without draining it or recording its unresolved owner. FINAL-007. |
| AC-018 | VERIFIED | Actual memory/file receipts, atomic JSON/CSV publication and admitted-provider failure tests pass; only publication commits. |
| AC-019 | VERIFIED | Direct acknowledgement loss, post-commit deadline and explicit writer-timeout controls pass with retained unknown-publication IDs. |
| AC-020 | VERIFIED | Existing logical/status/trace projection and boundary attribution tests pass. Missing native obligation is the AC-017/023 lifecycle root, not a duplicate trace finding. |
| AC-021 | VERIFIED | Recursive row/native-ref/unknown-receipt privacy controls and core metadata migration tests pass; no new wire payload is added. |
| AC-022 | VERIFIED | Closed consumer/runtime restrictions and existing explicit worker/compiler/control-plane tests pass; no durable adaptive qualification is claimed. |
| AC-023 | PARTIALLY SATISFIED | Concurrent artifact isolation and deferred final-consumer executor cleanup pass. A run can end with an unowned in-flight native worker and no PMADP523 obligation. FINAL-007. |
| AC-024 | PARTIALLY SATISFIED | Reviewed revision passes the original 98 cases locally and in all nine CI environments, plus wheel/docs/static gates. The two new required-behavior checks fail, so current proof cannot establish the full compatibility/native lifecycle contract. This is consequential to FINAL-007, not a reopened verifier defect. |

## Previous blockers

| Finding | Status | Verification |
|---|---|---|
| FINAL-001 | VERIFIED FIXED | Existing qualified all-unit analysis, unauthorized storage and replacement controls pass; admitted run-local pin dispatch remains unchanged. |
| FINAL-002 | VERIFIED FIXED | Required diamond/fanout/partial chain and both-direction distinct-port qualification tests pass. |
| FINAL-003 | VERIFIED FIXED | Real boundary/route tests pass. All four checkpoint retention controls pass; general finite timestamp validation inspected. |
| FINAL-004 | VERIFIED FIXED | Default/effective request, stored portable execution, scope, numeric policy and Profile precedence controls pass. |
| FINAL-005 | VERIFIED FIXED | Definite publication failure, acknowledgement loss, actual commit deadline and explicit writer timeout controls pass. |
| FINAL-006 | VERIFIED FIXED | Existing same-runtime concurrent logical artifact isolation test passes; not reopened. |
| FINAL-007 | PARTIALLY FIXED / REGRESSED | Prior native member timeout test passes. New native run-timeout owner test fails, and explicit async compiler compatibility regresses due the shared worker helper. |
| FINAL-008 | VERIFIED FIXED | Original non-writing verifier passes 98 cases; fabricated/skipped/tampered proof controls pass. Nine reviewed CI bundles match source and output digests. New failing checks invalidate qualification as expected, not by verifier malfunction. |
| FINAL-009 | VERIFIED FIXED | Existing recursive sensitive-row/native-ref/unknown-receipt projections pass. |
| SOL-010 | VERIFIED FIXED | Fresh documentation consistency passes and exact reviewed CI docs builds pass. |

## Remaining blocker

### FINAL-007 — Native cancellation lacks ownership and regresses explicit async compilers

Severity: **High**.
Disposition: **BLOCKER**.
Related AC: **AC-001, AC-017, AC-023**; consequential AC-024.

Location:

- `src/etlantic/runtime/dataframe_exec.py`, `_execute_portable`, worker call at lines 618–639.
- `src/etlantic/runtime/orchestrator.py`, `_execute_node` timeout obligation at lines 2294–2317 and `execute_physical` run timeout/cancellation handlers.
- Shared caller: `execute_dataframe_step` and `_run_node_once` invoke the same helper for explicit and adaptive portable dataframe execution.

Problem:

1. `abandon_on_cancel=True` returns from the host await while native work can
   remain active. The new obligation is appended only when `_execute_node`
   catches `TimeoutError`. A run deadline instead cancels that await with the
   cancellation exception; the outer physical run handler constructs a terminal
   report, bypassing the new owner bookkeeping. No native executor cleanup entry
   compensates for the abandoned built-in worker.
2. `_execute_portable` is shared with explicit `/1`; the worker branch is
   unconditional. The public asynchronous compiler method is now awaited inside
   `anyio.run` on a separate event loop. An explicit compiler using a
   pre-existing host-loop asynchronous session/resource fails even though the
   previous implementation awaited it successfully on its host loop. The Luna
   report's claim that this helper is used only by adaptive execution is false.

Evidence:

- Run the real qualified Polars chain with `run_seconds=0.3`, no step timeout,
  and `abandon_after_seconds=0.1`. At the real `apply_action` boundary, retain the
  original operation/result and hold it until a test release event. The report
  returns failed with no sink effect, while the native operation is still in
  flight. `etlantic.cleanup_obligations` is empty and PMADP523 is absent. The
  test releases and drains the injected worker in `finally` even when it fails.
  Thus the verification itself leaves no worker/patched operation behind.
- Run public explicit `arun_pipeline` with the real Polars compiler wrapped to
  await a pending host-loop Future completed asynchronously by the host. The
  current helper yields a partial run, PMEXEC422 and “Future attached to a
  different loop”; the sink is empty. Loading the unmodified helper from
  `git show 44a2ce24:src/etlantic/runtime/dataframe_exec.py` into a temporary
  in-memory module and running the same wrapper yields `succeeded`, sink id=1.
  No repository production file was changed for that differential control.

Relationship to current change: Both defects are in the latest native deadline
remediation of FINAL-007. The run-owner gap violates the existing native
lifecycle requirement; the explicit failure is a regression introduced by that
remediation, not unrelated plugin redesign work.

Why it matters / why this blocks the current change: The approved change must
either drain native work safely or retain ownership/reconciliation obligations
when abandoning it. Silent in-flight work cannot be reconciled from the terminal
report. It must also preserve explicit public compiler extension behavior. The
current change violates both obligations; green synchronous first-party tests
and a member-timeout test do not establish run-cancellation ownership or async
extension compatibility.

Required behavior:

- Handle native worker ownership on every relevant cancellation/deadline path,
  including run deadline/external cancellation. Drain safely or report an actual
  unresolved owner with PMADP523; fence late results and preserve in-flight buffers.
- Preserve explicit `/1` asynchronous compiler execution with its host resources.
  Keep adaptive native deadline mechanics within their authorized compatibility
  boundary. No particular threading/executor implementation is required.
- Keep the already-fixed native step deadline, one-attempt/no-timeout-retry,
  downstream suppression, cooperative executor cancel/cleanup, receipts and
  concurrent isolation behaviors passing.

Acceptance criteria for resolution: Both new tests pass naturally; the existing
native step deadline and awaited lifecycle tests remain passing; the complete
five-family campaign and relevant explicit compiler/runtime tests pass. There
must be no success/publication from cancelled native work, no unreported live
native owner, and no explicit async resource migration to an incompatible loop.

Verification artifacts in
`tests/runtime/test_sol_0_53_contract_rereview.py`:

- `test_final_007_native_run_timeout_drains_or_records_owner`
- `test_final_007_explicit_async_compiler_retains_host_resources`

Verification status: **FAIL — EXPECTED BLOCKER VERIFICATION**, two failures for
the reasons above. The previous native member deadline case passes.

**ESCALATION RECOMMENDED:** This root has survived multiple fixes that covered
individual cancellation sites. Use a stronger implementation model or focused
architectural review of native work ownership and the explicit/adaptive call
boundary. Keep the escalation bounded to FINAL-007; no runtime-wide redesign
or unrelated follow-up work is required.

## Quality gates and verification audit

Fresh local environment: Darwin arm64, Python 3.11.15 and exact qualified
backend versions. Repository was clean at review start. Gates run before review
additions are explicitly identified; their source-bound success is not reused
as proof of the subsequently expanded tree.

| Gate | Executed | Result / classification |
|---|---|---|
| Protected Sol suites before additions | Yes, locally | PASS — 35 passed, one existing wire warning. |
| Original non-writing 0.53 verifier | Yes, locally before additions | PASS — 98 executed/pass, source_changed=false; original source fingerprint and output digests match. |
| Configured core marker selection | Yes, locally before additions | PASS — 1,848 passed, 5 existing skips, 388 deselected, 48 warnings. Historical evidence regeneration check included and passed. |
| Ruff check / format | Yes, locally before and after additions | PASS; 945 Python files already formatted in final check. |
| Configured Pyright | Yes, locally before additions | PASS — zero errors/warnings; only tool update notice. |
| Documentation consistency | Yes, locally | PASS, including public surface/diagnostic/protocol/CLI/example/anchor checks. Only its existing ignored URL report is written. |
| New FINAL-007 tests | Yes, locally | EXPECTED BLOCKER VERIFICATION — two failures, 15 deselected. |
| Expanded 0.53 campaign, temporary review output | Yes, locally after additions | 98 passed, 2 EXPECTED BLOCKER VERIFICATION failures, 100 executed; source_changed=false. Protected subset: 35 passed, 2 failed. |
| Explicit helper differential control | Yes, temporary in-memory runtime exercise | Previous helper succeeds with the same host-resource compiler; current helper fails. CHANGE-CAUSED compatibility regression established. |
| GitHub CI for exact reviewed revision | Independently retrieved | PASS — all 37 jobs, [run 34792793787](https://github.com/eddiethedean/etlantic/actions/runs/34792793787), exact headSha c9d1986a. Includes optional compiler/backend suites, wheel/build, strict docs, security/static and other configured checks. These precede the new tests. |
| Required nine CI environment bundles | Independently downloaded/validated | 98/98 executed/pass in every Linux/macOS/Windows × Python 3.11/3.12/3.13 bundle; source fingerprint, scenario/JUnit contents and stdout/stderr/JUnit SHA-256 checked. Not claimed as local execution on other OSes. |

The expanded campaign evidence is
`/tmp/sol053-c9-expanded-review-evidence/qualification.json`, bound to source
`sha256:2b76ce9dcaaa827a5426d8fe32130858c3fa17ccadd6ec5dfdfcd358cf564cdf`.
All 100 cases executed; only the two new FINAL-007 tests fail. Committed passing
proof/support artifacts are not regenerated to hide failures. Their reviewed
98-case success does not qualify the subsequently expanded verification tree.

How the green suite could still be wrong was challenged concretely. The previous
new native test only exercises a member timeout, which enters the local
`TimeoutError` handler where the owner is recorded. Run cancellation follows a
different exception path. First-party dataframe compilers also have synchronous
bodies, so their green explicit baseline does not test the supported async
compiler protocol with a host-bound resource. The new tests exercise these
distinct contracts and retain the real native compiler results.

## Follow-ups and observations

New substantive FOLLOW-UP findings: **None**. Existing plan follow-ups #83/#86
remain outside remediation. No duplicate issue is created for this existing
release blocker. No new observations require implementation.

## Convergence and handoff

- FINAL-003 is newly VERIFIED FIXED; nine of ten historical blocker IDs are now
  VERIFIED FIXED, including the previously resolved FINAL-006.
- One blocker remains: **FINAL-007**.
- New blocker IDs: zero. One substantive explicit-extension regression is
  attributable to its latest remediation and retained under the same finding.
- New follow-ups: zero.
- The loop is smaller (two remaining roots reduced to one), but native work
  ownership and explicit compatibility need the focused escalation above.

Only FINAL-007 enters Luna/Terra remediation. Preserve all protected tests; run
the complete campaign after fixing production and regenerate only source-bound
evidence required by its unchanged verification process. Obtain a normal Sol
PASS before a final release check.

**NEEDS FIXES**
