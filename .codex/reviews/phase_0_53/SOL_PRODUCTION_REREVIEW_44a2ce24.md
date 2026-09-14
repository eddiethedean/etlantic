# Sol production re-review — phase 0.53

Reviewed production revision: `44a2ce24b8594fdcee548b8611e204336f3fe761`.
Verdict: **NEEDS FIXES**.

## Contract reconstruction and scope

Authority remains [IMPLEMENTATION_PLAN_0_53.md](../../../docs/11_DEVELOPMENT/IMPLEMENTATION_PLAN_0_53.md),
its REQUIRED BEHAVIOR, AC-001–AC-024 and verification matrix. Reviewed the original
review, `SOL_PRODUCTION_REREVIEW_7150f226.md`, the admission/boundary remediation,
remaining-blocker and CI repair reports, and the completed implementation report
at `/tmp/etlantic053-final-resolution.md`. The implementation report's conclusion
was treated as a claim to verify.

The boundary is Experimental static local `/2` execution: Local, Polars, Pandas
and the two directional Arrow families; closed named logical/port patterns;
whole-DAG admission; stored physical scheduling; actual boundary operations;
member lifecycle; publication receipts; privacy; explicit `/1` compatibility.
SQL/Spark adaptive execution, durable/control-plane acceptance, new optimization,
producer-skipping cache behavior and repository-wide repair remain non-scope.

Current packaged rows admit singleton/unfused physical realizations. Fused
realizations are explicitly rejected instead of inheriting singleton evidence;
this review makes no claim of qualified fused execution. No wider graph, backend
version or maturity claim is authorized.

Compared the actual change against `v0.52.1`, inspected public dispatch,
planning/lowering, packaged support, live admission, host adaptation, physical
protocol, scheduling, boundary operations, publication and affected dataframe
plugins. Inspected relevant tests, docs, packaging and CI. Python remains >=3.11;
the required CI matrix is 3.11/3.12/3.13 on Linux/macOS/Windows. Qualification uses
Polars 1.42.1, Pandas 2.3.3 and Arrow 25.0.0, with core/plugin distributions 0.52.1
on this development base. No database migration is introduced.

No substantive unrelated refactor, unauthorized dependency change or unrelated
behavioral expansion was established. The historical evidence refresh and CI
dependency-preservation repair follow the explicit request to make CI pass.

This review changes **only verification**: five cases appended to the existing
Sol contract file and this report. Production, old assertions, fixtures,
configuration, packaging and committed qualification artifacts are unchanged.

## Acceptance criteria

| AC | Status | Independent evidence / remaining gap |
|---|---|---|
| AC-001 | VERIFIED | Core compatibility suite, codec/protocol gates and protected explicit writer-timeout control pass. `/1` dispatch remains separate. |
| AC-002 | VERIFIED | Five-family stored differentials, real branch/dual-port and partial-scope tests pass; SDK/definition/CLI dispatch inspection shares the admitted local route. Exact support matcher and unsupported-consumer controls remain closed. |
| AC-003 | VERIFIED | Default/effective-request planning, historical wire/core controls, stored portable round trip, marker integrity and incomplete boundary rejection pass. |
| AC-004 | VERIFIED | Qualified all-unit analysis precedes session; unqualified storage and malformed operation descriptors reject before effects. Admission pins all applicable selected dependencies before host entry. |
| AC-005 | VERIFIED | Exact identity/version/capability/evidence and binding/contract checks inspected; protected controls pass. An additional qualified post-admission map replacement exercise uses only the original pin. |
| AC-006 | VERIFIED | Public protocol/result identity, routed executor input/output and deferred cleanup tests pass; original public LocalScheduler callers pass Pyright. Analysis is before execution effects. |
| AC-007 | VERIFIED | Request/scope equality and source/step partial scope controls pass; stored implementations are used rather than live authored/native bodies. |
| AC-008 | VERIFIED | Stored dependency scheduler inspected; transitive no-start, branching and distinct routed boundary tests pass. Complete result validation precedes registration/readiness. |
| AC-009 | VERIFIED | Protected numeric-policy and Profile-precedence controls pass. Batches use stored topology and captured bounded concurrency. |
| AC-010 | VERIFIED | Five-family typed-empty/nullable real-backend differentials pass. Sink preparation remains separate from publication; unqualified fused signatures reject. |
| AC-011 | VERIFIED | Both real Arrow directions and two distinct directional routes pass; the transfer-location sentinel proves conversion occurs inside the stored transfer unit. |
| AC-012 | VERIFIED | Five-family row-bound success/failure cases pass; actual finite collection checks rows/serialized bytes and preserves the transferred consumer value. |
| AC-013 | VERIFIED | Real local/Polars/Pandas passing/failing validation barriers pass, including failed logical attribution and zero affected publication. Closed descriptors reject unknown policy fields. |
| AC-014 | NOT SATISFIED | Checkpoint write/hit and finite expired-state control pass. Nonfinite stored retention is accepted as a hit and can publish cached rows. FINAL-003 remains open. |
| AC-015 | PARTIALLY SATISFIED | Unsafe retry admission and existing attempt controls pass; fused signatures remain unqualified. The admitted native member deadline is ignored rather than producing a timed-out/abandoned member. FINAL-007. |
| AC-016 | VERIFIED | Protected transitive dependency failure and branch-family controls pass; independent branches retain terminal logical outcomes. |
| AC-017 | NOT SATISFIED | Awaited executor cancel/cleanup under deadline passes. Synchronous native work blocks cancellation delivery and returns successful late output that reaches publication, without abandonment/obligation. FINAL-007. |
| AC-018 | VERIFIED | Admitted-provider definite failure, memory receipts, real JSON/CSV scheduler publication and concurrent atomic file overwrite controls pass. Only publication performs sink commits. |
| AC-019 | VERIFIED | Direct acknowledgement loss and actual post-commit deadline controls pass; receipt/unknown IDs are retained before sink success, with explicit timeout compatibility restored. |
| AC-020 | VERIFIED | Logical differential projections, summaries, stored unit traces, routed executor outcomes and boundary attribution controls pass. New deadline failure is lifecycle, not a second attribution root. |
| AC-021 | VERIFIED | Protected native-row/ref/receipt projections and core namespace-migration tests pass. Additional admitted typed-failure synthetic-row exercise emits only a safe generic report diagnostic. |
| AC-022 | VERIFIED | Existing consumer/core compatibility tests pass; public compile/external/durable rejection paths and static support restrictions inspected. No adaptive durable qualification is claimed. |
| AC-023 | VERIFIED | Protected same-runtime concurrent artifact isolation and qualified executor final-consumer cleanup pass. Run-local maps and stable per-run receipt identities inspected. Native deadline gap remains specifically AC-017. |
| AC-024 | PARTIALLY SATISFIED | Original 93-case campaign passes locally and in nine CI environments; source/output digests independently match. Docs, wheel import and static gates pass. The expanded campaign now contains expected failing FINAL-003/007 verification and cannot qualify release until those requirements pass. |

## Previous blockers

| Finding | Status | Verification |
|---|---|---|
| FINAL-001 | VERIFIED FIXED | All-unit qualified analysis and unauthorized storage rejection pass. Fresh qualified map replacement: all three units analyze the admitted executor, execution/cleanup use only that executor. |
| FINAL-002 | VERIFIED FIXED | Exact five-edge diamond, fanout, source/step slices and directional ports pass; independently packaged 13-row qualification inspected. |
| FINAL-003 | PARTIALLY FIXED | Real collection/validation/checkpoint/reuse and result routing now execute. New persisted-retention invariant fails twice, with two meaningful passing controls. |
| FINAL-004 | VERIFIED FIXED | Effective/default request, source-only scope, stored portable execution, numeric policies and Profile concurrency precedence pass; original public scheduler test typing passes. |
| FINAL-005 | VERIFIED FIXED | Definite failure, direct ack loss, post-commit deadline and explicit legacy timeout controls all pass; atomic file receipts also pass. |
| FINAL-006 | VERIFIED FIXED | Previously resolved concurrent same-runtime source-barrier control still passes; not reopened. |
| FINAL-007 | PARTIALLY FIXED | Awaited shielded cancel/cleanup and deferred executor lifetime pass. New native member deadline/fencing verification fails on the admitted real compiler path. |
| FINAL-008 | VERIFIED FIXED | Tampered/fabricated/skipped-proof controls pass; fresh original non-writing campaign and nine environment bundles verified. Current proof rejection after new review tests is expected, not another defective verifier root. |
| FINAL-009 | VERIFIED FIXED | All existing recursive row/native-ref/unknown receipt controls pass; fresh admitted typed-failure report projection does not leak the synthetic marker. |
| SOL-010 | VERIFIED FIXED | Unchanged docs consistency and official strict docs build pass; evidence page states Experimental. |

## Remaining blocker findings

### FINAL-003 — Persisted checkpoint retention is not validated before reuse

Severity: **Medium**.
Disposition: **BLOCKER**.
Related AC: **AC-014**; consequential release evidence AC-024.

Location: `src/etlantic/runtime/physical_operations.py:205–237`,
`execute_boundary.read_checkpoint`.

Problem: Checkpoint metadata validation verifies keys/schema but not the types or
finiteness of persisted timestamps. Python's JSON decoder accepts NaN/Infinity.
The sole expiry comparison is `expires_at <= now`; this is false for NaN and
positive infinity, so malformed retention grants a checkpoint hit.

Evidence: Public `LocalScheduler.execute` runs a qualified local source→sink
plan with a stored reuse unit. The producer returns id=1; the same-plan,
same-contract, correctly digested checkpoint holds id=99. With finite expired
metadata, reuse selects the producer and publishes id=1. With NaN expiry, reuse
succeeds, selects the checkpoint and publishes id=99. Infinity has the same
failure. The regression test uses synthetic rows only and no mocked storage,
dataframe, scheduler or reuse operation.

Relationship to current change: This is the new adaptive checkpoint read/barrier
implementation and the same incomplete-boundary validation root as FINAL-003.
It is not an unrelated cache-hardening task.

Why it matters / why this blocks the current change: The approved AC explicitly
requires malformed persisted state to fail without placement. Instead, invalid
retention authorizes cached data to reach publication. Correct content digest
alone does not establish valid retention metadata. The changed reuse functionality
therefore violates an in-scope data-consistency requirement despite green hit tests.

Required behavior: Validate the complete persisted checkpoint metadata before
granting any hit. Timestamps must conform to the writer's finite numeric/null
contract; malformed metadata fails the reuse boundary and prevents affected
publication. Preserve valid no-expiry hits and safe expired/stale/missing
selection of the already-planned producer. Do not insert/replan work or weaken
integrity/authorization checks.

Acceptance criteria: Both malformed-retention cases fail safely with no sink
effect; unexpired/expired controls retain current outcomes; existing checkpoint,
integrity/security and real backend cases remain passing. Validate at the general
persisted-metadata boundary, rather than special-case these two constants.

Verification artifact:
`tests/runtime/test_sol_0_53_contract_rereview.py::test_final_003_checkpoint_retention_must_be_valid_before_reuse`.

Verification status: **FAIL — EXPECTED BLOCKER VERIFICATION**: NaN and infinity
cases fail because the reuse trace says succeeded/checkpoint; unexpired and
finite-expired controls pass.

### FINAL-007 — Native work can ignore the member deadline and publish late output

Severity: **High**.
Disposition: **BLOCKER**.
Related AC: **AC-015, AC-017**; consequential release evidence AC-024.

Location: `src/etlantic/runtime/orchestrator.py:2265–2283`;
`src/etlantic/runtime/dataframe_exec.py:601–620`;
`packages/etlantic-polars/src/etlantic_polars/compiler.py:284–317`.

Problem: The member deadline is an AnyIO cancel scope around an async function,
but the admitted portable compiler performs synchronous native actions directly
inside that async execution. Blocking work prevents deadline delivery. There is
no late-result/deadline check before the host records successful member output
and releases downstream work. A configured abandonment bound supplies no remedy
for this path.

Evidence: Inject 0.4 seconds of latency at the real Polars compiler's synchronous
`apply_action`, then run its original operation and return its real native result.
The approved request has step_seconds=0.1 and abandon_after_seconds=0.1. The
admitted first and second portable members both run, both report succeeded with
one attempt, and the memory sink publishes. No cleanup/abandonment obligation is
recorded. An earlier manual exercise with 0.08 seconds of native latency versus
0.01-second member deadline reproduced the same successful publication.

Relationship to current change: The underlying synchronous backend behavior also
exists outside adaptive execution; this finding is bounded to `/2` admission and
execution claiming the new deadline/drain/fencing contract. Existing explicit
runtime redesign is not requested. This is the native-lifecycle gap already
identified under FINAL-007, not a new finding ID.

Why it matters / why this blocks the current change: The approved contract makes
member timeout a hard deadline and requires late output to be fenced from
registration/publication, with safe draining or explicit ownership obligations.
The changed native path instead reports an entirely successful run and commits
after the admitted deadline. Passing cancellable fake executors cannot establish
this native requirement. Large native operations are a realistic source of this
latency, not a performance micro-optimization.

Required behavior: Establish enforceable member/run deadline handling around
admitted native work. Drain or abandon according to the existing contract,
preserve in-flight/borrowed buffers, and prevent expired/cancelled results from
registering or reaching publication. Attribute timeout/abandonment to the member,
block its dependents and never retry member timeout. Record PMADP523 owner
obligations when required. Preserve explicit `/1` compatibility and the already
passing awaited cancel/cleanup behavior. No particular thread/executor design is
prescribed by this verification.

Acceptance criteria: The entered slow native member becomes timed_out/abandoned
with one attempt; its downstream step is skipped; sink effects remain zero;
report is not succeeded. Existing native success, Arrow routing, timeout,
publication and cooperative lifecycle cases pass. Equivalent synchronous native
latency must satisfy the invariant without matching a particular sleep/input.

Verification artifact:
`tests/runtime/test_sol_0_53_contract_rereview.py::test_final_007_native_member_deadline_fences_late_output`.

Verification status: **FAIL — EXPECTED BLOCKER VERIFICATION**: first member is
succeeded instead of timed_out/abandoned; native action was entered and the real
result reached the sink.

## Quality gates and evidence audit

Fresh local environment: Darwin arm64, Python 3.11.15, exact qualified backend
versions above. Existing non-writing evidence checks ran before adding review
tests; those checks' success is not claimed for the subsequently expanded tree.

| Gate | Executed | Result / classification |
|---|---|---|
| Original full adaptive non-writing gate | Yes, before review additions | PASS: 93 executed/pass, no required skips. |
| Both protected Sol suites including five additions | Yes | 32 passed, 3 failed; all failures EXPECTED BLOCKER VERIFICATION under FINAL-003/007. |
| CI core marker selection | Yes, before additions | PASS: 1,844 passed, 5 existing skips, 387 deselected, 48 warnings. No tests were excluded beyond the repository's existing markers. |
| Dataframe/Polars/Pandas compiler marker selection | Yes | PASS: 57 passed, 21 deselected using `-m 'polars or pandas'`. This is the actual selected count, not a claimed 78-test full run. |
| Ruff check / formatting | Yes, before and after additions | PASS; 945 Python files formatted. |
| Configured Pyright | Yes, before and after additions | PASS: zero errors/warnings. |
| Original public scheduler caller typing | Yes | PASS: zero errors/warnings. |
| Additional Pyright on entire Sol contract file | Yes | Five pre-existing verification annotation errors; the identical five reproduce from `git show HEAD` in a temporary file. No new function typing errors; this file is outside the configured gate. Not a production blocker. |
| Documentation consistency | Yes | PASS, including surface/diagnostic/protocol/docs checks. It writes only its existing ignored URL report. |
| Official strict docs build | Yes | PASS; site output `/tmp/sol053-current-site`. |
| Historical 0.52 evidence | Yes, before additions | PASS: 10 artifacts, 18 acceptance criteria. No historical artifacts rewritten by review. |
| Pipeline codec burn-in | Yes | PASS: 32 fixtures, eight versions. |
| Stable-foundation acceptance | Yes | PASS: 21/21. |
| Plugin manifests / release checks | Yes | PASS. These checks do not approve adaptive execution. |
| Security matrix / surface / diagnostics / protocol / agent guidance | Yes | PASS; security inventory does not substitute for runtime adversarial verification. |
| Core wheel build and isolated import | Yes | PASS: core/physical protocol import, 13 packaged support rows; Polars/Pandas/Arrow absent in isolated environment. |
| Qualified post-admission executor map mutation | Yes, manual runtime exercise | PASS: only the original qualified executor is analyzed/executed/cleaned. |
| Typed backend failure synthetic-row report projection | Yes, manual runtime exercise | PASS: marker absent, generic PMADP520 diagnostic retained. |
| Non-writing 0.53 gate after first review additions | Yes | FAIL: correctly rejects stale committed proof after protected source changes. EXPECTED REVIEW-SOURCE DRIFT, not a new verifier defect. |
| Expanded qualification campaign, temporary evidence output | Yes | 95 passed, 3 failed, 98 executed cases, source_changed=false. All failures are the new FINAL-003/007 tests. See `/tmp/sol053-review-evidence/qualification.json`; no committed support/proof artifacts regenerated. |
| GitHub CI at reviewed production HEAD | Independently retrieved | PASS: all 37 jobs in [run 34789790498](https://github.com/eddiethedean/etlantic/actions/runs/34789790498), exact headSha 44a2ce24. These precede the new tests and do not prove their requirements. |
| Required environment proof | Independently checked downloaded artifacts | All nine OS/Python bundles: 93 passing/non-skipped cases, matching source fingerprint, JUnit/stdout/stderr SHA-256 and scenario validation. Not a local execution claim for other OSes. |

The previous three fixture corrections retain their assertions and supply
qualified identity/capability/evidence or inject failure through the admitted
memory provider. They legitimately reach the intended paths instead of requiring
unqualified providers. However, the existing replacement test can pass through
early admission rejection; the additional qualified manual exercise above was
needed to independently establish the real pinning behavior.

How the green suite could still be wrong was tested concretely: existing reuse
coverage mainly writes and reads a valid checkpoint in one run, and lifecycle
coverage mainly uses awaitable cancellation checkpoints. Malformed persisted
retention and synchronous native latency violate the requirements despite the
93 green cases. Neither test mocks around the production behavior it verifies.

## Follow-ups and observations

New substantive FOLLOW-UP findings: **None**. No issue is created for an
observation or for these bounded release blockers. Existing plan follow-ups
#83/#86 and broader adaptive epic work remain outside this remediation.

Low / OBSERVATION: The qualified post-admission pinning exercise could become a
permanent focused test, since the existing replacement test admits early
rejection. The current fix is independently demonstrated, so this is not handed
to implementation as another blocker.

Low / OBSERVATION: Extra static checking of the older Sol contract file exposes
five existing annotation defects outside configured gates. They do not invalidate
the runtime assertions or require production remediation.

## Convergence and handoff

- Seven of the nine previously open blockers are VERIFIED FIXED.
- FINAL-006 remains independently VERIFIED FIXED from the earlier review.
- Two blockers remain: **FINAL-003 and FINAL-007**.
- New blocker IDs: zero. No new substantive regression caused specifically by
  the final fixture corrections or CI dependency repair was established.
- New follow-ups: zero.
- The loop is converging: topology/admission/routing/publication/privacy/evidence
  and docs roots now have substantially stronger passing proof. Remediation is
  restricted to persisted checkpoint metadata validation and native deadline/
  late-result lifecycle handling.

**ESCALATION RECOMMENDED:** FINAL-007's native lifecycle root survived previous
attempts that fixed only awaited hooks. Use a stronger implementation model or
a focused architectural review of the admitted native invocation boundary.
Additional variations of fake cancellable executors will not resolve it.
FINAL-003 needs a bounded complete persisted-metadata validator, not cache or
runtime redesign. Keep both fixes within the existing approved contract.

Only FINAL-003 and FINAL-007 enter Luna/Terra remediation. Preserve the protected
new tests; after production fixes, run the full campaign and regenerate only
source-bound evidence required by its unchanged verification process. Obtain a
normal Sol PASS before a final release check.

**NEEDS FIXES**
