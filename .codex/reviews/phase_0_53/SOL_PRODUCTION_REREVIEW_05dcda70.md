# Sol production re-review — phase 0.53

Reviewed production: `05dcda70b3c3dea14a767a7b630a851df6e3f9e1`.
Verdict: **NEEDS FIXES**.

## Contract and scope

Authority remains `docs/11_DEVELOPMENT/IMPLEMENTATION_PLAN_0_53.md`, REQUIRED BEHAVIOR, AC-001–AC-024 and its verification matrix. Reconstructed the contract from that plan, previous review/remediation history, current production, protected verification, real-backend fixtures, documentation, packaging and CI. Audited the latest production remediation against `a0937f48`: the implementation change is confined to executor failure projection and retaining the scheduler's deferred error across independent batches.

Scope remains Experimental, fixture-qualified static local `/2` execution with Local, Polars, Pandas and one directional Arrow cut. Exact named topology/port qualification remains required. Explicit `/1` compatibility, metadata-only artifacts, fail-closed admission and existing historical serialization remain authoritative. SQL/Spark adaptive execution, durable/control-plane acceptance, wider graphs, unqualified fusion, producer-skipping caches, medallantic migration work and repository cleanup remain outside scope. No new dependency, migration or public wire change is required by this remediation. Runtime remains Python >=3.11; packaging on this v0.52.1 development base remains 0.52.1.

This review modifies only the existing protected test to add one privacy variant, and this report. Production, existing assertions, committed proof, configuration and package metadata remain unchanged.

## Acceptance criteria

Evidence includes fresh original protected verification, the expanded 119-case campaign, code inspection and independently retrieved exact-head CI. The campaign exercises real Local/Polars/Pandas adapters, both Arrow directions, native lifecycle and qualified physical units.

| AC | Status | Evidence |
|---|---|---|
| AC-001 | VERIFIED | Independent explicit dispatch and compatibility controls pass; host execution identity inspected. |
| AC-002 | VERIFIED | Five qualified families, exact diamond/fanout/partial chains and distinct directional ports pass; unmatched support rejects. |
| AC-003 | VERIFIED | Stored request/portable round trips and marker/envelope tamper controls pass; historical gates pass in exact-head CI. |
| AC-004 | VERIFIED | Whole-DAG support/storage denial controls pass before session/effects. |
| AC-005 | VERIFIED | Exact adapter identity/version/evidence/binding and live replacement controls pass; pin enforcement inspected. |
| AC-006 | VERIFIED | Metadata analysis, result identity/routing and now terminal returned executor failures pass. SOL-011 is fixed. |
| AC-007 | VERIFIED | Effective/default request, stored execution, source-only/partial selection and no-widening controls pass. |
| AC-008 | VERIFIED | Stored dependency and transitive no-start controls pass; failed branch publication remains suppressed. |
| AC-009 | VERIFIED | Numeric policy, Profile precedence and bounded scheduling controls pass. |
| AC-010 | VERIFIED | Real typed empty/nullable portable and sink-preparation differentials pass; no unqualified fusion claim. |
| AC-011 | VERIFIED | Both real Arrow directions, distinct routing and transfer-unit fencing pass. |
| AC-012 | VERIFIED | Actual finite collection and bounds success/failure controls pass. |
| AC-013 | VERIFIED | Actual contracts/barriers suppress affected publication; schema deadline controls pass. |
| AC-014 | VERIFIED | Checkpoint/reuse/retention and private boundary/file rollback controls pass. |
| AC-015 | VERIFIED | Member attempts, unsafe-policy rejection and preparation/deadline controls pass. |
| AC-016 | VERIFIED | SOL-011 now produces terminal failed/one-attempt left, skipped left sink and successful independent right publication. |
| AC-017 | VERIFIED | Native drain/owner obligation, member fence, boundary deadline and cleanup controls pass. |
| AC-018 | VERIFIED | Actual memory/JSON/CSV publication, no-write, receipts and destination-lock controls pass. |
| AC-019 | VERIFIED | Late committed receipt, ack loss, unknown obligations and explicit writer compatibility pass. |
| AC-020 | VERIFIED | Failed physical unit and failed logical member now agree; summary accounts for all six members and retains PMADP520. |
| AC-021 | REGRESSED | Protocol serializers pass, but new raw host failure-stage projection serializes synthetic private row content. FINAL-009. |
| AC-022 | VERIFIED | Unsupported consumers/targets/durable/dynamic paths reject; qualification claims remain bounded. |
| AC-023 | VERIFIED | Concurrent isolation, repeated cleanup and safe owner obligations pass; every executor started by the new probe is cleaned. |
| AC-024 | PARTIALLY SATISFIED | Exact-head CI and original proof pass; expanded required privacy verification fails. Proof must be refreshed after remediation, not to certify this failure. |

## Previous blockers

| Finding | Status | Verification |
|---|---|---|
| FINAL-001 | VERIFIED FIXED | All-unit admission, live storage replacement and metadata append-mode controls pass. |
| FINAL-002 | VERIFIED FIXED | Exact named topology and directional-port qualification pass. |
| FINAL-003 | VERIFIED FIXED | Real collection/validation/checkpoint/reuse and retention controls pass. |
| FINAL-004 | VERIFIED FIXED | Effective/default request, stored portable scope and concurrency controls pass. |
| FINAL-005 | VERIFIED FIXED | Committed late receipt, ack-loss/unknown, explicit writer and publication controls pass. |
| FINAL-006 | VERIFIED FIXED | Same-runtime concurrent artifact isolation passes. |
| FINAL-007 | VERIFIED FIXED | Native/member/run/boundary deadline, fencing, rollback and owner cleanup controls pass. |
| FINAL-008 | VERIFIED FIXED | Tampered/fabricated/skipped-evidence rejection passes; expanded campaign honestly reports its one failed case. |
| FINAL-009 | REGRESSED | Existing recursive protocol/receipt tests pass; newly changed host failure projection bypasses their safe serializer. |
| SOL-010 | VERIFIED FIXED | Fresh documentation consistency and strict build pass. |
| SOL-011 | VERIFIED FIXED | Original terminal-outcome variant passes. Actual fix preserves failed outcomes before raising and retains deferred errors across later independent batches. |

## Release blocker

### FINAL-009 — Returned executor failure metadata bypasses safe report projection

Severity: **High**.
Disposition: **BLOCKER**.
Related AC: **AC-021**, consequential **AC-024**.

Location: `src/etlantic/runtime/orchestrator.py:1626–1629` copies `outcome.failure_stage` directly into node state. `_step_report` at line 2345 copies that value directly into `StepRunReport.failure_stage`. The safe protocol projection in `src/etlantic/runtime/physical_protocol.py`, `PhysicalLogicalOutcome.to_dict`, is used for metrics but bypassed for the failure stage.

Problem: The newly added terminal-failure projection accepts executor-controlled failure metadata into the persisted/public report without the protocol's metadata-only sanitization. Valid terminal outcomes and safe diagnostics do not make arbitrary string payloads safe to serialize.

Evidence: The exact admitted Local Fanout executor returns an identity-valid failed unit and failed left outcome with one attempt, PMADP520 and synthetic `failure_stage='rows=[{"id":"SOL_PRIVATE_ROW_MARKER"}]'`. The final report is partial, correctly counts four succeeded/one failed/one skipped, suppresses the left sink, publishes the independent right sink exactly once and cleans every started executor. It nevertheless contains `SOL_PRIVATE_ROW_MARKER` in the serialized left failure stage. Direct `PhysicalLogicalOutcome.to_dict()` safely hashes this same value; the host path bypasses that projection. No actual private rows or secrets were used.

Relationship to current change: Raw projection was introduced by the latest SOL-011 remediation (`89ff6e47`). Before remediation, the failed executor result was rejected before this logical stage was copied. This is concrete new evidence reopening the established FINAL-009 privacy invariant, not a renamed finding or renewed architectural preference.

Why it matters: Run reports are externally observable and persisted. A plugin/executor may attach row-bearing context to failure metadata. This path exposes that context even though the public protocol serializer excludes it.

Why this blocks the current change: AC-021 explicitly excludes rows, resolved secrets and native references from recursive public projections. The changed supported executor/report path violates that privacy contract. Blocker tests 1, 2 and 4 apply. Shipping a known report-persistence disclosure in the newly changed failure path is not justified by passing successful-executor or direct-serializer tests.

Required behavior: Validate or safely project executor-controlled failure metadata before assigning it to logical/public report state. Preserve ordinary safe `transform` attribution, terminal outcomes, attempts, dependent skips, independent publication, diagnostics, receipts and cleanup. Correct the shared metadata projection boundary; do not special-case the fixture or marker.

Acceptance criteria for resolution:

1. The existing terminal-outcome variant retains `failure_stage="transform"`, one failed attempt, PMADP520 and truthful partial summary.
2. The row-bearing variant does not expose the synthetic marker anywhere in `json.dumps(report.to_dict())`.
3. Both variants retain zero left sink effects, one independent right sink effect and cleanup of every started executor.
4. Protected verification and related quality gates pass; refresh source-bound qualification only after the production fix and all required tests pass.

Verification artifact: `tests/runtime/test_sol_0_53_contract_rereview.py::test_sol_011_failed_executor_branch_has_terminal_logical_report[final-009-private-stage]`. One privacy variant was added to the existing integration fixture without weakening its assertions or mocking the production scheduler/report path.

Verification status: **FAIL — EXPECTED BLOCKER VERIFICATION**. Targeted `-k 'sol_011 or final_009'`: one failed, two passed, 19 deselected. All terminal/count/effect/cleanup assertions pass before the private-marker assertion fails. Expanded campaign: 119 executed, 118 passed, one failed, zero skips, `source_changed=false`.

## Quality gates and verification audit

Local environment: Darwin arm64, Python 3.11.15, Polars 1.42.1, Pandas 2.3.3, PyArrow 25.0.0. CI is independently retrieved evidence, not claimed as local execution.

| Gate | Executed | Result |
|---|---|---|
| Original protected contract re-review | Local, before addition | PASS — 21/21. |
| Historical protected re-review | Local, after addition | PASS — 20/20, one warning. |
| Targeted SOL-011/FINAL-009 | Local, after addition | Two pass; one EXPECTED BLOCKER VERIFICATION failure. |
| Expanded 0.53 campaign, temporary proof | Local | FAIL — EXPECTED BLOCKER VERIFICATION; 118/119 pass, zero skips, source unchanged. |
| Initial non-writing 0.53 campaign | Local | INVALIDATED — 118/118 tests pass, but verification source changed during execution when the privacy variant was added. Not claimed as passing source-bound proof. |
| Configured core marker suite | Local | 1,854 passed, five existing skips, 402 deselected, 48 warnings; one evidence-regeneration failure caused by this review's added verification source. Committed-input hash independently matches committed evidence. |
| Optional dataframe/compiler/conformance | Local | PASS — 62 passed, 194 deselected. |
| Ruff / formatting / configured Pyright | Local, after addition | PASS — 947 files formatted; zero type errors/warnings. |
| Documentation consistency / strict build | Local | PASS — strict output in temporary directory. |
| Surface / diagnostics / protocol / manifests / security / release | Local | PASS — six existing static gates. |
| Core sdist / wheel / isolated optional-free imports | Local | PASS — 0.52.1 built into temporary directory; core/physical protocol import without Polars/Pandas/PyArrow and direct safe failure serialization pass. |
| Medallantic migration goldens | Local current, isolated a0937f48 and isolated v0.52.1 | FAIL — PRE-EXISTING/UNRELATED; identical three fingerprint discrepancies, one plan golden passes. SOL-012. |
| Exact-head CI | Independently retrieved | PASS — run 34842187681, head 05dcda70, all 37 jobs successful; predates added review verification. |
| Additional OS/runtime and optional package gates | CI evidence | Passed exact-head CI; not repeated locally. |

The green suite was challenged at the newly changed executor-to-logical-report trust boundary. Existing direct serializer and receipt tests do not exercise this raw host stage assignment; their green results are genuine but incomplete. The new integration variant establishes the underlying privacy invariant using the existing admitted executor. No gates, discovery rules or assertions were weakened. Committed evidence remains unchanged.

The core failure is `test_final_052_006_evidence_regenerates_cleanly`, not a runtime assertion. The historical verifier includes tracked tests in its source hash. Recomputing its input hash with the committed version of the only modified tracked file yields `sha256:9573d1e9bfc453010a9a86194a140a632f6744cd423aa743c9e831b6fb333638`, exactly matching committed historical evidence. The review addition invalidates that binding; refresh it after blocker remediation. This is review-verification-induced evidence drift, not a second production defect or a pre-existing failure.

A fresh non-writing `_payloads()` comparison independently regenerated all nine historical JSON artifacts: each differs only in `repository_revision`; their scenario results, plan fingerprints, platform declarations and side-effect counts agree. No historical artifact was rewritten.

Expanded proof: `/tmp/sol053-05dc-expanded-proof/qualification.json`, source `sha256:e0dced303f6adea525428fd39c77c4e70c5f6d510b16cd7ab17477ce3290b9a5`.

## Follow-ups

### SOL-012 — Pre-existing medallantic migration fingerprint golden discrepancies

Severity: **Low**.
Disposition: **FOLLOW-UP**.
Related AC: **NONE**.
Location: `tests/medallantic/test_migration_goldens_0_35.py:64`, `_definition_golden_payload` and migration definition golden fixtures.

Problem/evidence: Three generated definition fingerprints differ from expected goldens for bronze-auto, SparkForge ecommerce and SQL ecommerce. The same expected/observed hashes and three-fail/one-pass result were independently reproduced using isolated source archives of both `a0937f48` and `v0.52.1` in this installed environment, as well as current production. The cause needs investigation before changing goldens.

Relationship to current change: It predates phase 0.53 and concerns medallantic migration work outside this boundary. Exact-head CI is green, so platform/environment-sensitive fingerprint inputs are also worth investigating. It does not affect the qualified adaptive runtime or prevent its ACs from being met; no remediation is required for this release.

Why it matters: Reproducible migration fingerprints and trustworthy golden verification should not depend on unexplained environment drift.

GitHub status: **CREATED ISSUE #145** after open-issue duplicate search: https://github.com/eddiethedean/etlantic/issues/145. Reproducer, hashes, expected behavior and proposed verification are in the issue. No failing follow-up artifact was added to the branch.

Existing out-of-scope tracking #83/#86 remains separate. Observations: **None**.

## Convergence

- Latest previous blocker resolved: **one**, SOL-011.
- Historical findings verified fixed: **ten**; FINAL-009 is reopened with concrete regression evidence.
- Blockers remaining: **one**, FINAL-009.
- New blockers attributable to latest remediation: **one**, the reopened privacy root.
- New follow-ups discovered: **one**, SOL-012 / #145.
- The failure-retention defect is closed. Remaining remediation is bounded to safe failure metadata projection; no architecture redesign or unrelated cleanup is required.

Only **FINAL-009** enters Luna/Terra remediation. SOL-012 and observations do not enter the remediation loop. Obtain normal Sol PASS before another final release check.

**NEEDS FIXES**
