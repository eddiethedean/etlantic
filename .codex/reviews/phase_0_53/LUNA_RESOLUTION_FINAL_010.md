# Luna blocker remediation — phase 0.53

This remediation addresses only the blockers in Sol re-review `1b48168b`.

## FINAL-009 — Safe failure projection covers every physical host branch

Status: **FIXED**

Related AC: **AC-021**, consequential **AC-024**

Root cause: The physical host projected provider-controlled logical failure
stage and code directly into node state in the successful-unit branch. The
terminal failed-unit branch had already been changed to use the protocol's
safe projection, but the sibling branch still bypassed it.

Production changes: `src/etlantic/runtime/orchestrator.py`, both physical
outcome projection loops in `LocalOrchestrator._execute_physical_units` now
derive failure stage, code, and metrics from one `PhysicalLogicalOutcome.to_dict()`
result. The sanitized code/stage values are also used for the raised terminal
error attribution.

Before-fix verification: `tests/runtime/test_sol_0_53_contract_rereview.py::test_sol_011_failed_executor_branch_has_terminal_logical_report[final-009-inconsistent-unit-private-stage]`
failed because `SOL_PRIVATE_ROW_MARKER` appeared in `report.to_dict()` through
the successful-unit/failed-member path.

After-fix verification: The same protected test passes. The full expanded
0.53 campaign passes all 120 scenarios with no skips and `source_changed=false`.

Related regression tests: `tests/runtime/test_sol_0_53_contract_rereview.py`,
`tests/runtime/test_sol_0_53_rereview.py`, and
`tests/runtime/physical/test_qualification_0_53.py` — 93 passed.

Additional tests: None; the protected Sol verification already covers the
new sibling path and preserves the original valid failed-unit cases.

Resolution: Every reachable physical logical-outcome projection now uses the
existing metadata-only wire projection. Arbitrary row-bearing failure text is
hashed/redacted before it can reach public step reports or terminal error
attribution, while valid failure codes, stages, counts, independent
publication, and cleanup behavior remain unchanged.

## FINAL-008 — Committed 0.53 proof is current and substantiated

Status: **FIXED**

Related AC: **AC-024**

Root cause: The committed adaptive 0.53 qualification bundle retained the
source revision and 118-scenario record from before the latest protected
verification fixture and production fix.

Production changes: Regenerated the committed companions under
`docs/11_DEVELOPMENT/evidence/adaptive_0_53/` (`qualification.json`,
`qualification.stdout.txt`, `qualification.stderr.txt`, and `qualification.xml`)
from the passing source-bound campaign. Refreshed the historical 0.52
fingerprints through `scripts/check_adaptive_0_52.py --write` because the
protected test fixture is included in that source revision as well.

Before-fix verification: `uv run --no-sync python scripts/check_adaptive_0_53.py`
rejected the committed bundle as stale; it recorded 118 scenarios and the old
source revision.

After-fix verification: The same non-writing verifier exits zero. The recorded
bundle contains 120 executed/passing scenarios, source revision
`sha256:9821cc94f32bde6611414fb1c5566ed373f84ffeb5a915b540fc7842bf1733f`,
and matching JUnit/stdout/stderr digests. The historical 0.52 verifier also
passes with all 10 artifacts current.

Related regression tests: Full 0.53 source-bound campaign — 120/120 passed;
configured core marker suite — 1855 passed, 5 skipped, 403 deselected.

Additional tests: None.

Resolution: The checked-in proof is regenerated only after the complete
campaign passes without skips or source mutation, and the default verifier
now confirms the committed source, environment, scenario identities, JUnit,
stdout, and stderr digests without rewriting them.

## Follow-ups

Existing Sol follow-up SOL-012 / GitHub issue #145 (pre-existing medallantic
migration fingerprint discrepancies) remains outside this remediation scope.
No new follow-up candidates were introduced.

## Quality gates

- `uv run --no-sync pytest -q tests/runtime/test_sol_0_53_contract_rereview.py tests/runtime/test_sol_0_53_rereview.py tests/runtime/physical/test_qualification_0_53.py` — PASS (93 tests).
- `uv run --no-sync pytest -q -m 'not medallantic and not polars and not pandas and not sql and not spark and not real_pyspark and not airflow and not prefect and not keyring and not sqlmodel and not datafusion'` — PASS (1855 passed, 5 skipped, 403 deselected).
- `uv run --no-sync python scripts/check_adaptive_0_53.py` — PASS.
- `uv run --no-sync python scripts/check_adaptive_0_52.py` — PASS.
- Ruff check/format, Pyright, documentation, release, surface, diagnostic,
  protocol, security, and agent-guidance gates — PASS.

Blockers received: 2  
Blockers fixed: 2  
Blockers remaining: 0  
Verification conflicts: 0  
Escalations: 0  
New follow-up candidates: 0

**READY FOR SOL RE-REVIEW**
