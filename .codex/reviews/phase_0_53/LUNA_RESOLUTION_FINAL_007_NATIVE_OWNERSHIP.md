# Luna resolution — FINAL-007 native ownership and explicit compatibility

Authoritative remediation set:
[SOL_PRODUCTION_REREVIEW_c9d1986a.md](SOL_PRODUCTION_REREVIEW_c9d1986a.md).
Only FINAL-007 is assigned. FINAL-003 and all other previously resolved blockers
remain outside this remediation. The protected review additions are carried
forward unchanged.

## FINAL-007 — Native cancellation lacks ownership and regresses explicit async compilers

Status: **FIXED**

Related AC: AC-001, AC-017, AC-023; consequential AC-024. Existing AC-015 member
timeout/no-retry behavior is preserved.

Root cause: The shared portable helper unconditionally moved the public async
compiler coroutine onto a new worker event loop, including explicit execution.
Native ownership bookkeeping was attached to the member `TimeoutError` handler,
which run deadline/external cancellation bypassed. Worker completion and queued
cancellation were not tracked at the actual native invocation. Synchronous
output validation could also exceed a deadline after native completion without
a final cancellation/deadline fence before artifact registration.

Production changes:

- `src/etlantic/runtime/native_execution.py`, `NativeExecution.run`: invocation
  completion/start gates, shielded draining with the captured abandonment bound,
  and safe actual unit/member/attempt owner obligations when work remains active.
  Cancellation before worker start prevents later execution. The worker closure
  retains native inputs until completion, and cancelled results never return.
- `src/etlantic/runtime/dataframe_exec.py`, `_execute_portable`: explicit callers
  directly await the compiler on the host loop; only adaptive callers supplied
  with an owned invocation use a worker. `execute_dataframe_step` delivers
  cancellation/checks the effective deadline before returning validated output
  for registration.
- `src/etlantic/runtime/orchestrator.py`, `_run_node_once`: supplies native
  ownership only in physical mode using the stored compute-unit identity and
  member attempt. Removed the generic timeout-handler obligation, which could
  invent an owner even when native work had finished.
- `scripts/check_adaptive_0_53.py`: adds the implementation-side native lifecycle
  file to the executed/source-bound qualification set and existing CI matrix.
  No gate or required scenario is removed.
- `docs/06_EXECUTION/EXECUTION_MODEL.md`: documents adaptive drain/abandonment,
  owner metadata, late-result fencing and explicit asynchronous compatibility.

Before-fix verification: Both protected tests
`test_final_007_native_run_timeout_drains_or_records_owner` and
`test_final_007_explicit_async_compiler_retains_host_resources` were reproduced
and failed. The first returned with in-flight work and empty obligations; the
second failed with a Future attached to a different loop. The later
implementation-side output-validation reproducer also demonstrated late success
and publication before the final deadline fence was added.

After-fix verification: Both protected tests pass, as does
`test_final_007_native_member_deadline_fences_late_output`. The final qualification
campaign executes/passes all 105 cases, including 37 protected Sol cases and all
five new implementation cases; `source_changed=false`.

Related regression tests: Both complete protected Sol suites, five-family stored
differentials, real Arrow directions/ports, retry admission, awaited executor
cancel/cleanup, artifact lifetime, publication/acknowledgement and concurrent
isolation tests pass within the executed campaign. The final core suite passes
1,851 cases with 5 existing skips; the fresh non-writing evidence gate passes all
105 cases against the committed proof.

Additional tests in `tests/runtime/test_native_execution.py`:

- Full drain without an abandonment bound and completion within a finite bound
  (two parameter cases): cancelled output never returns, completed work leaves
  no fabricated obligation.
- Worker-capacity cancellation: queued native work never starts afterward and
  leaves no fabricated obligation.
- Public external cancellation: terminal cancellation preserves the actual
  stored unit/member/attempt obligation and zero sink effect.
- Deadline during synchronous output validation: timed-out member, no retry,
  dependent skipped, no registered member output or publication, and no unresolved
  worker obligation when native work has already finished.

Resolution: Cancellation ownership now lives at the actual adaptive native await
and is independent of which outer handler receives it. Owned work drains fully
without a bound or yields a PMADP523 owner record after the configured bound.
Late native/validated output is fenced. Explicit async compilers retain their
host loop and resources. This resolves the prior escalation recommendation
within the approved architecture; no runtime-wide redesign is introduced.

## Requirements self-check

| Requirement | Status | Evidence |
|---|---|---|
| Explicit async compiler compatibility (AC-001) | IMPLEMENTED | Protected host-resource compiler test |
| Native member/run/external cancellation and late fencing (AC-017) | IMPLEMENTED | Three protected native/compatibility cases, external cancellation and validation-fence tests |
| Owned/shared buffers and actual unresolved owner IDs (AC-023) | IMPLEMENTED | Worker closure lifetime, completion/start gates, actual unit/member/attempt assertion, existing shared lifetime/isolation tests |
| Executed source-bound qualification (AC-024) | IMPLEMENTED locally | 105 passing/non-skipped scenarios; fresh verifier and exact CI result provided with handoff |
| No member-timeout retry (AC-015 compatibility) | IMPLEMENTED | Protected native deadline one-attempt assertion |
| Documentation | IMPLEMENTED | Execution-model cancellation paragraph and documentation gates |
| Dependencies / packaging / migrations | IMPLEMENTED / unchanged contract | No new dependency or persistence migration; core wheel builds/imports without optional backends |

## Follow-up report

Existing Sol FOLLOW-UPs: none newly assigned. Existing plan tracking #83/#86 is
not implemented. Observations are not implemented.

New follow-up candidates: **None**. The validation fence is required by the same
late-result invariant and is part of FINAL-007, not adjacent feature work.

Known contract limitation: An abandoned native thread can continue until its
operation finishes. Its buffers remain held, its result is fenced, and its owner
obligation remains in the terminal report. Forceful thread termination and
cross-run/crash-resumable reconciliation are not introduced.

## Quality gates

| Gate | Executed | Result | Notes |
|---|---|---|---|
| Before-fix protected targeted tests | Yes | FAIL — OPEN BLOCKER | Two expected failures reproduced before production edits |
| After-fix protected native/async tests | Yes | PASS | Three protected cases |
| Complete protected suites + initial implementation cases | Yes | PASS | 41 cases before adding the fifth validation-fence case |
| Final focused native/compatibility run | Yes | PASS | 9 passed, 13 deselected |
| Final qualification write campaign | Yes | PASS | 105 executed/pass, zero required skips, no source drift |
| Historical adaptive evidence refresh | Yes | PASS | Unchanged 10-artifact / 18-AC verifier; only source fingerprints refreshed |
| Interim core suite | Yes | FAIL — CHANGE CAUSED, resolved | 1 historical fingerprint failure while final fence was being added; final stable rerun required |
| Final stable core suite | Yes | PASS | 1,851 passed, 5 skipped, 392 deselected, 48 existing warnings |
| Final non-writing qualification | Yes | PASS | 105/105 executed/pass; committed proof matches source; source_changed=false |
| Ruff check / formatting | Yes | PASS | 947 Python files formatted; no gate weakened |
| Configured Pyright | Yes | PASS | Zero errors/warnings |
| Extra typing: new helper, implementation tests, qualifier | Yes | PASS | Zero errors/warnings after fixing new test import sites |
| Documentation consistency | Yes | PASS | Existing ignored URL report only |
| Strict documentation build | Yes | PASS | Site output in temporary directory |
| Core wheel build / isolated import | Yes | PASS | Native helper and physical protocol import with Polars/Pandas/Arrow absent |

All final local gates above pass. A prior revision's CI is not used as evidence
for these fixes; exact pushed-revision CI is reported with the handoff.

## Scope / remaining issues

Protected Sol assertions, fixtures and verification semantics are unchanged.
Only one additional qualification file is required; discovery has been expanded,
never excluded. No unrelated refactor, dependency change, release-version change,
schema migration, FOLLOW-UP fix or OBSERVATION implementation is included.

No known unresolved implementation issue remains within FINAL-007. No
verification conflict or architectural escalation remains.

Blockers received: 1
Blockers fixed: 1
Blockers remaining: 0
Verification conflicts: 0
Escalations: 0
New follow-up candidates: 0

**READY FOR SOL RE-REVIEW**
