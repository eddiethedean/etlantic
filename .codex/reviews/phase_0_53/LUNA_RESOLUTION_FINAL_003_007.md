# Luna blocker resolution — phase 0.53

This remediation addresses only the two blockers in
`SOL_PRODUCTION_REREVIEW_44a2ce24.md`: FINAL-003 and FINAL-007. Production
implementation, protected verification, and source-bound historical evidence
were updated only where required by those blockers and the resulting quality
gates.

## FINAL-003 — Persisted checkpoint retention is not validated before reuse

Status: **FIXED**

Related AC: AC-014.

Root cause: The checkpoint reader checked metadata keys and content integrity,
but accepted JSON non-finite numeric constants for `created_at` and
`expires_at`. Comparisons with NaN or positive infinity could therefore select
malformed cached rows.

Production changes: `src/etlantic/runtime/physical_operations.py`,
`execute_boundary()` now validates both timestamps as non-boolean finite numbers
(`expires_at` may remain null) before authorization, integrity selection, or
materialization.

Before-fix verification: `test_final_003_checkpoint_retention_must_be_valid_before_reuse`
failed for NaN and infinity; each malformed checkpoint was reported as a
successful reuse hit. Finite unexpired and expired controls passed.

After-fix verification: The same test passes all four cases. Malformed
retention fails before sink publication; valid unexpired metadata selects the
checkpoint and finite expired metadata selects the planned producer.

Related regression tests: `tests/runtime/physical/test_qualification_0_53.py`
checkpoint/reuse cases and all protected Sol suites pass.

Additional tests: The two malformed timestamp cases establish the distinct
finite-metadata invariant while retaining both valid-state controls.

Resolution: Persisted checkpoint retention is now validated at the shared read
boundary, so malformed state cannot authorize cached data or introduce a new
execution path.

## FINAL-007 — Native work can ignore the member deadline and publish late output

Status: **FIXED**

Related AC: AC-015, AC-017.

Root cause: First-party compiler methods had an async signature but performed
synchronous dataframe operations directly on the event loop. A member timeout
could not be delivered until the native operation returned, after which the
result was registered and published.

Production changes: `src/etlantic/runtime/dataframe_exec.py` executes the
compiler coroutine in a cancellable AnyIO worker boundary with
`abandon_on_cancel=True`; an abandoned result is never returned to artifact
registration. `src/etlantic/runtime/orchestrator.py` records a PMADP523 native
owner obligation for timed-out physical steps, fences late results, and keeps
timeout attempts from retrying.

Before-fix verification: `test_final_007_native_member_deadline_fences_late_output`
entered the real Polars compiler with controlled synchronous latency, then
observed successful late member execution and sink publication despite a
shorter member deadline.

After-fix verification: The same test passes. The slow admitted native member
is timed out/abandoned after one attempt, its downstream member is skipped, the
sink remains empty, and the report is not successful.

Related regression tests: All 35 protected Sol tests, all 63 affected adaptive
planner/physical tests, and existing explicit/core tests pass. Qualified
executor cancellation/cleanup and output-lifetime tests remain passing.

Additional tests: The real compiler-path latency test establishes behavior at
the synchronous native operation boundary; it does not replace the existing
awaitable executor lifecycle tests.

Resolution: Native execution no longer blocks the host event loop, deadlines
produce terminal timeout/abandonment rather than late success, and abandoned
results cannot reach physical artifacts or publication. Explicit `/1` behavior
is unchanged because the worker boundary is used by the adaptive dataframe
execution path.

## Quality gates

| Gate | Result |
|---|---|
| Protected Sol suites | PASS — 35 tests |
| Affected adaptive/planner/physical suite | PASS — 63 tests |
| Phase 0.53 qualification | PASS — 98 executed/pass, source-bound evidence clean |
| Ruff check and format | PASS |
| Configured Pyright | PASS — zero errors/warnings |
| Historical adaptive 0.52 evidence | PASS — refreshed with the changed source fingerprint |
| Historical evidence regeneration test | PASS |
| Existing core suite | PASS after evidence refresh — 1,848 passed, 5 skipped, 388 deselected |

The previous GitHub run at the pre-remediation commit is not reused as proof of
these production fixes; a new CI run is required after handoff.

## Scope and remaining issues

No FOLLOW-UP or OBSERVATION was implemented. No verification conflict or
architecture escalation remains. The review-only verification additions are
retained for Sol’s re-review. No known unresolved implementation issue remains
within the two assigned blockers.

Blockers received: 2
Blockers fixed: 2
Blockers remaining: 0
Verification conflicts: 0
Escalations: 0
New follow-up candidates: 0

**READY FOR SOL RE-REVIEW**
