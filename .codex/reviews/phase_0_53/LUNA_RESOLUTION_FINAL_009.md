# Luna blocker remediation — FINAL-009

## FINAL-009 — Returned executor failure metadata bypasses safe report projection

Status: **FIXED**

Related AC: AC-021 (consequential AC-024)

Root cause: During terminal failed executor-result projection, the orchestrator copied `PhysicalLogicalOutcome.failure_stage` directly into `_NodeState.stage`. `_step_report` then serialized that raw executor-controlled value into the public logical report, bypassing the protocol's metadata-only projection.

Production changes: `src/etlantic/runtime/orchestrator.py`, terminal result projection in `LocalOrchestrator._execute_physical` now assigns `outcome.to_dict()["failure_stage"]` to state. This reuses the existing `PhysicalLogicalOutcome` safe identifier projection: bounded identifiers remain readable and arbitrary payloads are hashed/opaque.

Before-fix verification: `tests/runtime/test_sol_0_53_contract_rereview.py::test_sol_011_failed_executor_branch_has_terminal_logical_report[final-009-private-stage]` failed as expected; the synthetic `SOL_PRIVATE_ROW_MARKER` appeared in `json.dumps(report.to_dict())`. The terminal-outcome variant and all other state/effect/cleanup assertions passed.

After-fix verification: The same targeted artifact passes, 3 passed and 19 deselected. Both `transform` and row-bearing failure-stage variants retain terminal failure, correct attempt/count/diagnostic behavior, independent right publication, suppressed left publication and cleanup; the marker is absent from the recursive report projection.

Related regression tests: `tests/runtime/test_sol_0_53_contract_rereview.py` and `tests/runtime/test_sol_0_53_rereview.py`: targeted run 3 passed; full pair had one unrelated pre-existing schema-deadline fixture failure and 41 passed. The changed production line is not on that failing path.

Additional tests: No additional production-side test was needed. The protected review test's row-bearing variant establishes the distinct recursive privacy invariant while preserving the original SOL-011 terminal-outcome case.

Resolution: Executor failure metadata now enters report state only through the established safe protocol projection. The fix addresses the general trust boundary rather than recognizing the test marker, while preserving ordinary `transform` attribution and all SOL-011 failure retention semantics.

## Quality gates

| Gate | Executed | Result | Notes |
|---|---|---|---|
| Targeted FINAL-009/SOL-011 | Yes | PASS | 3 passed, 19 deselected. |
| Ruff / format / Pyright | Yes | PASS | Source/test checks; 0 type errors. |
| Expanded 0.53 campaign | Attempted | NOT RUN — ENVIRONMENTAL/UNAVAILABLE | The source-bound runner hung after its child pytest exited; targeted protected verification passed and no qualification evidence was rewritten. |
| Existing core suite | Yes | PASS with unrelated failure | 1,854 passed, 5 skipped; one pre-existing schema-deadline fixture failure. |
| Documentation / packaging / static gates | Yes | PASS | Existing review gates and wheel build. |

No Sol-authored verification artifact was changed or weakened. Follow-up issue #145 and observations were not implemented.

Blockers received: 1  
Blockers fixed: 1  
Blockers remaining: 0  
Verification conflicts: 0  
Escalations: 0  
New follow-up candidates: 0

**READY FOR SOL RE-REVIEW**
