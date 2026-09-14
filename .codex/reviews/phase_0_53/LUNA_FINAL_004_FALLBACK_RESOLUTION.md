# Phase 0.53 — FINAL-004 Remediation Report

Baseline: `5100e9c4a4fdfcb1d5304e1112590d02b881910e`.
Authority: `SOL_PRODUCTION_REREVIEW_5100e9c4.md` and
`docs/11_DEVELOPMENT/IMPLEMENTATION_PLAN_0_53.md`.
Remediation set: only FINAL-004. No production review or release approval is
claimed by this implementation-side report.

## FINAL-004 — Fallback reinterprets a resolved placement target as an engine

Status: **FIXED**

Related AC: **AC-001**. The earlier AC-003/AC-007 effective-input contracts
remain covered by the existing protected verification.

Root cause: Non-physical host mode covers two different request contracts.
Ordinary explicit requests contain engine names, while an independently
generated explicit fallback originates from an adaptive request containing
placement target IDs. The resolver applied ordinary explicit precedence to both
and replaced the fallback's resolved engine descriptor with its target ID.

Production changes: `src/etlantic/runtime/orchestrator.py`,
`LocalOrchestrator._resolve_implementation`, recognizes the existing versioned
`etlantic.adaptive_fallback` record. Physical execution and independent explicit
fallbacks use resolved descriptors. Ordinary explicit requests retain engine
override precedence. The original request is preserved for reporting; no new
public API, execution-mode flag, qualification row or dependency was added.

Before-fix verification:
`tests/runtime/test_sol_0_53_fallback_override.py::test_final_004_fallback_preserves_resolved_request_target`
failed: **1 failed in 58.52s**. Planning resolved target `qualified` to `local`;
execution attempted engine `qualified`, returned `partial`, and published no
rows. The observed failure matches the review finding.

After-fix verification: The same protected artifact passed unchanged in the
targeted run (**59 passed, 3 warnings, 35.59s**) and configured core run
(**1865 passed, 5 skipped, 407 deselected, 50 warnings, 185.03s**).

Related regression tests executed:

- `test_sol_0_53_explicit_override.py`: ordinary explicit engine `null` still
  selects the alternate native implementation and publishes ID 2.
- `test_sol_0_53_effective_request.py`: target precedence, unknown target
  rejection, and required parameters before validation.
- `test_sol_0_53_contract_rereview.py`, `test_sol_0_53_rereview.py`, and
  `test_adaptive_execution_0_53.py`: captured inputs, pinned descriptor authority,
  stored-plan execution, admission, concurrency and adjacent physical behavior.
- Entire configured core suite and the 128-scenario qualification campaign.

Additional tests:
`tests/runtime/test_fallback_request_0_53.py::test_stored_fallback_target_named_as_another_engine_keeps_planned_engine`
uses target ID `null` mapped to engine `local`, serializes and verifies the plan,
then executes through the shared host. It proves that a target ID colliding with
a valid alternate engine cannot silently redirect execution. Expected output is
ID 1, and the original request object and overrides remain unchanged. This
extends the review reproducer's unknown-engine failure with a serialization and
silent-wrong-implementation variant.

Resolution: The existing fallback record supplies the missing request-origin
distinction. The resolver uses the independently planned engine for fallback,
the admitted descriptor for physical execution, and late engine overrides for
ordinary explicit execution. Both error-producing and silently misrouting
fallback inputs satisfy the required behavior. No known unresolved
implementation issue remains in this blocker's scope.

## Documentation, evidence and scope check

`docs/10_REFERENCE/API_PLAN_RUNTIME.md` explains target IDs, fallback descriptor
authority, normal explicit precedence and the prohibition on stored `/2`
downgrade. There are no schema, migration, dependency, runtime-version or
packaging-metadata changes. Python remains >=3.11; existing dependency ranges
remain intact.

Historical source-bound evidence was regenerated after staging the two new
test files so they participate in its tracked-source fingerprint. Its ten
artifacts differ only in revision metadata. Adaptive 0.53 qualification was
regenerated after passing execution; only its source revision and observation
timestamp changed. Scenario identities, results, aggregate process digests and
sanitized JUnit digest are unchanged. Both default non-writing verifiers pass.

The final diff contains the single resolver change, one API documentation
paragraph, the unchanged Sol-authored reproducer, one implementation-side test,
and source-bound evidence metadata. Existing protected tests, CI, discovery,
assertions and gate configuration were not modified or weakened. Existing local
review notes were preserved.

## Follow-Up Report

Existing Sol FOLLOW-UPs: #145 (Medallantic golden migration fingerprints) and
#146 (deadline-test timing sensitivity) remain separate; neither was remediated.

New Follow-Up Candidates: None.

## Quality Gate Report

All commands use the existing environment, with `uv run --no-sync` where
applicable. Logs are `/tmp/luna053-final004-*.log`.

| Gate | Executed | Result | Notes |
|---|---|---|---|
| Protected and adjacent targeted tests | Yes | PASS | 59 passed, including both fallback cases and explicit/adaptive controls |
| Configured core marker suite | Yes | PASS | 1865 passed; existing optional skips and deselections retained |
| Adaptive 0.53 evidence generation | Yes | PASS | 128/128 executed scenarios; no source change during campaign |
| Adaptive 0.53 default non-writing verifier | Yes | PASS | Fresh 128/128 execution; source and committed evidence match |
| Historical adaptive 0.52 generation and non-writing verifier | Yes | PASS | 10 artifacts, 18 criteria |
| Ruff lint | Yes | PASS | Whole repository |
| Ruff formatting verification | Yes | PASS | 951 files formatted |
| Configured Pyright | Yes | PASS | 0 errors, 0 warnings |
| Explicit Pyright for changed source and both fallback tests | Yes | PASS | 0 errors, 0 warnings |
| Documentation consistency | Yes | PASS | Internal links/anchors; external URLs inventoried, not fetched |
| Documentation build | Yes | PASS | Site built under /tmp |
| Release metadata checks | Yes | PASS | Existing 0.52.1 development-base metadata |
| Surface inventory | Yes | PASS | Existing exports and lazy namespaces |
| Diagnostic stability | Yes | PASS | Existing inventory and tiers |
| Protocol freeze | Yes | PASS | Six stable core /1 families |
| Plugin manifests | Yes | PASS | Existing manifests unchanged |
| Security matrix | Yes | PASS | Existing controls and verification references |
| Agent guidance drift | Yes | PASS | Existing guidance unchanged |
| Stable foundation | Yes | PASS | Coverage 21/21; 21 tests passed |
| Core sdist/wheel build | Yes | PASS | Built under /tmp |
| Isolated core wheel import | Yes | PASS | Physical protocol imports without Polars or Pandas |
| Final diff whitespace check | Yes | PASS | Working and staged diffs |

Linux/Windows and Python 3.12/3.13 were not executed during this local
remediation. No fresh remote CI result is claimed. This is implementation
verification and handoff; independent Sol review remains required.

## Remediation Summary

Blockers received: 1

Blockers fixed: 1

Blockers remaining: 0

Verification conflicts: 0

Escalations: 0

New follow-up candidates: 0

**READY FOR SOL RE-REVIEW**
