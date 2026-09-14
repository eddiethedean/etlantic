# Luna — Blocker Resolution Report

## SOL-011 — Failed executor branch disappears from final logical report

**Status:** FIXED  
**Related AC:** AC-016 (also AC-006, AC-020)

**Root cause:** A non-successful physical executor result was raised before its
per-logical-member outcomes were projected into the run state. In addition,
scheduler errors were retained only within the current batch, allowing a later
independent success to replace the failure before report construction.

**Production changes:** `src/etlantic/runtime/orchestrator.py`

- Project and validate `logical_outcomes` for every member before raising the
  physical-unit error, preserving terminal status, attempts, metrics, failure
  stage, and diagnostic code.
- Retain the first scheduler error across batches and raise it only after all
  independent runnable units have drained, so the final report includes the
  failure while independent side effects remain observable.

**Before-fix verification:** Protected test
`tests/runtime/test_sol_0_53_contract_rereview.py::test_sol_011_failed_executor_branch_has_terminal_logical_report`
failed. The failed branch remained `pending` with zero attempts, the summary
reported zero failed steps, and no `PMADP520` diagnostic was emitted.

**After-fix verification:** The same protected test passes. The failed branch is
terminal with one attempt and its `PMADP520` diagnostic; the independent branch
still succeeds and publishes its sink effect; cleanup completes for both.

**Related regression tests:**

- `tests/runtime/test_sol_0_53_contract_rereview.py`: 21 passed
- `tests/runtime/test_sol_0_53_rereview.py`: 20 passed
- `tests/runtime/physical/test_qualification_0_53.py`: 50 passed
- `tests/runtime/test_native_execution.py`: 14 passed
- `tests/runtime/test_adaptive_execution_0_53.py`: 7 passed

**Additional tests:** None added by Luna. The protected SOL-011 regression is
the focused verification artifact for this blocker.

**Resolution:** Failed executor outcomes now become terminal logical report
entries before the executor exception propagates. Outcome shape and attempt
validation fail closed with a safe terminal diagnostic. Scheduler failures are
preserved while unrelated work drains, preventing later successes from erasing
the failure from the final report.

## Follow-Up Report

No existing Sol follow-ups were changed. No new follow-up candidates were
identified during remediation.

## Quality Gate Report

| Gate | Executed | Result | Notes |
|---|---:|---|---|
| SOL-011 targeted regression plus prior blocker regressions | Yes | PASS | 3 passed |
| Contract rereview suite | Yes | PASS | 21 passed |
| Sol rereview suite | Yes | PASS | 20 passed, 1 pre-existing warning |
| Physical qualification suite | Yes | PASS | 50 passed, 10 pre-existing warnings |
| Native execution suite | Yes | PASS | 14 passed |
| Adaptive execution suite | Yes | PASS | 7 passed |
| Ruff check and format check | Yes | PASS | 947 files formatted; no violations |
| Pyright | Yes | PASS | 0 errors, 0 warnings |
| Adaptive 0.52 evidence verification | Yes | PASS | 10 artifacts, 18 criteria |
| Adaptive 0.53 evidence verification | Yes | PASS | 118/118 scenarios; source unchanged |
| Full repository pytest suite | Yes | FAIL — PRE-EXISTING/UNRELATED | 2,229 passed, 29 skipped; 3 migration golden fingerprint mismatches in `tests/medallantic/test_migration_goldens_0_35.py`, outside the changed runtime path |

## Remediation Summary

Blockers received: 1  
Blockers fixed: 1  
Blockers remaining: 0  
Verification conflicts: 0  
Escalations: 0  
New follow-up candidates: 0

**READY FOR SOL RE-REVIEW**
