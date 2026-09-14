# Luna blocker remediation — phase 0.53

## FINAL-009 — Identifier-shaped failure stages still disclose provider data

Status: **FIXED**

Related AC: **AC-021** (consequential AC-024)

Root cause: The existing `_identifier` projection intentionally preserved
bounded lexical identifiers for trusted identity fields. Failure stages are
executor-controlled text, but both `PhysicalLogicalOutcome.to_dict()` and
`PhysicalUnitFailure.to_dict()` reused that permissive behavior. A data-bearing
stage that matched the identifier pattern therefore reached the public report.

Production changes: `src/etlantic/runtime/physical_protocol.py` adds the
closed `_SAFE_FAILURE_STAGES` vocabulary and `_failure_stage()` projection.
Known runtime stages remain readable; every unknown string is hashed directly,
and non-string values become opaque. Both logical-outcome `failure_stage` and
physical-failure `stage` use this projection. No orchestrator branch, public
API, stored identity or receipt format was changed.

Before-fix verification: Sol's protected
`tests/runtime/test_sol_0_53_contract_rereview.py::test_sol_011_failed_executor_branch_has_terminal_logical_report[final-009-identifier-shaped-private-stage]`
failed. `rows:SOL_PRIVATE_ROW_MARKER` survived `PhysicalLogicalOutcome.to_dict()`
and appeared in the recursive report after all terminal-count, effect and
cleanup assertions passed.

After-fix verification: The same protected test and all sibling cases pass;
the expanded protected Sol suites report **44 passed, one warning**. The full
source-bound adaptive campaign reports **121/121 scenarios passed** with
`source_changed=false`. Direct protocol checks confirm `transform` remains
readable while the identifier-shaped stage becomes a `sha256:` value for both
logical and physical failure projections.

Related regression tests: `tests/runtime/test_sol_0_53_rereview.py` and
`tests/runtime/test_sol_0_53_contract_rereview.py` — 44 passed, one warning;
`tests/runtime/physical/test_qualification_0_53.py` — 50 passed, 10 warnings;
configured core marker suite — 1,855 passed, 5 skipped, 404 deselected.

Additional tests: The protected identifier-shaped stage case establishes the
missing semantic input class through the admitted executor, physical
scheduler, terminal report, independent publication and cleanup path. No
duplicate production-side test was added.

Resolution: Failure-stage serialization no longer infers trust from lexical
shape. The shared protocol boundary preserves the established finite runtime
vocabulary and hashes arbitrary executor-controlled stage text before it can
enter reports or failure summaries. Existing terminal retention, attribution,
publication, reconciliation and cleanup behavior remains intact.

## FINAL-008 dependency

After the production fix and protected verification passed, the committed
0.53 qualification companions were regenerated together and the historical
0.52 fingerprints were refreshed. Both default non-writing verifiers pass.
The 0.53 bundle records 121 executed/passing scenarios, source revision
`sha256:6aaaa08cadd74d6817d912c72f78e0ecfa340104f3eb72cc334aa51cc8f4e642`,
and matching JUnit/stdout/stderr hashes.

## Follow-ups

Existing Sol follow-up SOL-012 / GitHub issue #145 (pre-existing medallantic
migration fingerprint discrepancies) remains outside this remediation scope.
No new follow-up candidates were introduced. No Sol verification artifact was
weakened or disabled.

## Quality gates

| Gate | Executed | Result | Notes |
|---|---|---|---|
| Protected Sol review suites | Yes | PASS | 44 passed, one warning. |
| Full adaptive 0.53 campaign | Yes | PASS | 121/121, no skips, `source_changed=false`. |
| Default adaptive 0.53 evidence verifier | Yes | PASS | Committed bundle current and substantiated. |
| Historical adaptive 0.52 verifier | Yes | PASS | 10 artifacts, 18 acceptance criteria. |
| Configured core marker suite | Yes | PASS | 1,855 passed, 5 skipped, 404 deselected. |
| Physical qualification suite | Yes | PASS | 50 passed. |
| Ruff / format / Pyright | Yes | PASS | 947 files, zero type errors. |
| Surface / diagnostics / protocol / manifests / security / release / agent guidance | Yes | PASS | Existing gates pass. |
| Stable foundation / portable 0.50 evidence | Yes | PASS | Existing compatibility gates pass. |
| Docs consistency / strict build | Yes | PASS | Built successfully to temporary output. |
| Core sdist / wheel and optional-free import | Yes | PASS | Built/imported successfully. |
| Exact-head CI | No | NOT RUN — new commit | Previous exact-head CI was green; push below triggers new CI. |

## Remediation summary

Blockers received: 1  
Blockers fixed: 1  
Blockers remaining: 0  
Verification conflicts: 0  
Escalations: 0  
New follow-up candidates: 0

**READY FOR SOL RE-REVIEW**
