# Sol production re-review — phase 0.53

Reviewed production: `1b48168b5c58e358a263c9c3d69ac01f61eba8b7`.
Verdict: **NEEDS FIXES**.

## Contract and scope

Authority remains `docs/11_DEVELOPMENT/IMPLEMENTATION_PLAN_0_53.md`, its REQUIRED BEHAVIOR, AC-001–AC-024, verification matrix and explicit non-scope. Read the complete current request, approved contract, previous Sol reviews and latest Luna report; inspected current implementation, protected tests, serialization/reporting, package/CI configuration and documentation. Latest production diff against `05dcda70` is one safe failure-stage projection at line 1627. Historical generated 0.52 evidence was refreshed; committed 0.53 qualification was not.

The release boundary remains Experimental, fixture-qualified static local `/2` execution on Local, Polars, Pandas and one directional Arrow cut. Exact named topology/port qualification, fail-closed admission, stored physical scheduling, publication-only commits, safe metadata and explicit `/1` compatibility remain sticky. SQL/Spark adaptive execution, durable/control-plane acceptance, unqualified graphs/fusion, producer-skipping caches, medallantic migration repair and 0.54 availability graduation are outside scope. No new dependency, migration, public API or broad refactoring is required.

This review changes only one protected verification fixture by adding a third case. Production, existing cases/assertions, configuration and committed evidence are preserved. This report records review evidence; it does not approve the implementation or refresh failing proof.

## Acceptance criteria

Fresh original protected tests: 42 passed. Exact-head CI: 37/37 jobs passed on the reviewed commit. The new probe exercises the actual admitted executor, physical scheduler, independent memory publication, logical report and cleanup path.

| AC | Status | Evidence |
|---|---|---|
| AC-001 | VERIFIED | Explicit identity/default/no-adaptive controls and compatibility CI remain passing. |
| AC-002 | VERIFIED | Required five families and exact topology/port support controls pass in protected/qualified tests and CI. |
| AC-003 | VERIFIED | Stored request/portable serialization and marker/envelope tamper/historical controls remain passing. |
| AC-004 | VERIFIED | Whole-DAG admission, final-dependency/storage denial and zero-effect controls remain passing. |
| AC-005 | VERIFIED | Exact live authorization/identity/version/capability/binding/evidence replacement controls and pin inspection remain valid. |
| AC-006 | VERIFIED | Metadata analysis, exact result identity, supported protocol dispatch and explicit executor compatibility remain passing. |
| AC-007 | VERIFIED | Effective/default request, stored/partial/source-only scope and no-widening controls pass. |
| AC-008 | VERIFIED | Dependency/transitive no-start controls pass; the new malformed-result probe suppresses the failed branch's publication. |
| AC-009 | VERIFIED | Captured concurrency/numeric-policy/Profile precedence controls remain passing. |
| AC-010 | VERIFIED | Real portable typed empty/null and sink-preparation differentials remain passing; no native/fusion widening. |
| AC-011 | VERIFIED | Real Arrow directions, distinct port routing, exact conversion and transfer fencing remain passing. |
| AC-012 | VERIFIED | Actual finite collection/bounds controls remain passing. |
| AC-013 | VERIFIED | Validation/barrier/publication suppression controls pass. Isolated schema-deadline control is recorded below. |
| AC-014 | VERIFIED | Checkpoint/reuse/retention, safe boundary rollback and producer-path controls remain passing. |
| AC-015 | VERIFIED | Member attempts, policy rejection and timeout/retry controls remain passing. |
| AC-016 | VERIFIED | All three returned-outcome probes retain failed left, skipped left sink and independent right success with truthful terminal totals. |
| AC-017 | VERIFIED | Original native/member/run/boundary fencing, owner/lifetime and cleanup controls pass; one load-sensitive campaign exercise is classified below. |
| AC-018 | VERIFIED | Actual memory/file publication, no-write, receipt-before-success and destination-lock controls remain passing. |
| AC-019 | VERIFIED | Known late receipt/ack-loss/unknown obligation/explicit writer controls remain passing. |
| AC-020 | VERIFIED | Failed logical member and physical failure agree; partial summary accounts for all six selected members. |
| AC-021 | NOT SATISFIED | Original privacy variant passes, but inconsistent successful-unit/failed-member result reaches a second raw stage projection. FINAL-009. |
| AC-022 | VERIFIED | Unsupported consumer/target/durable/dynamic rejection and truthful qualification claims remain. |
| AC-023 | VERIFIED | Run isolation/repeated cleanup/owner obligations remain passing; every executor started by the new probe is cleaned. |
| AC-024 | PARTIALLY SATISFIED | CI/runtime/wheel/docs evidence passes, but expanded privacy verification and the required committed non-writing gate fail. FINAL-009 / FINAL-008. |

## Previous blockers

| Finding | Status | Verification |
|---|---|---|
| FINAL-001 | VERIFIED FIXED | Original whole-DAG/all-unit/live-storage/metadata denial controls pass. |
| FINAL-002 | VERIFIED FIXED | Exact named topology and directional-port qualification controls pass. |
| FINAL-003 | VERIFIED FIXED | Real boundary execution, checkpoint/reuse and retention controls pass. |
| FINAL-004 | VERIFIED FIXED | Effective request/default/stored partial scope and concurrency controls pass. |
| FINAL-005 | VERIFIED FIXED | Late committed receipt, unknown/ack-loss and explicit writer/publication controls pass. |
| FINAL-006 | VERIFIED FIXED | Same-runtime concurrent isolation controls pass. |
| FINAL-007 | VERIFIED FIXED | Original protected deadline/fencing/cleanup cases pass; isolated timing check below. |
| FINAL-008 | PARTIALLY FIXED | Verifier still rejects stale/fabricated/skipped proof, but committed 0.53 proof does not match this production/test revision. |
| FINAL-009 | PARTIALLY FIXED | First failed-unit host projection is safe; second inconsistent-result projection still leaks. |
| SOL-010 | VERIFIED FIXED | Fresh docs consistency and strict build pass. |
| SOL-011 | VERIFIED FIXED | Terminal reports/attempts/totals, independent publication and retained deferred error pass in all probes. |

## Remaining blockers

### FINAL-009 — Safe failure projection covers only one host branch

Severity: **High**.
Disposition: **BLOCKER**.
Related AC: **AC-021**, consequential **AC-024**.

Location: `src/etlantic/runtime/orchestrator.py:1804–1806` assigns raw `outcome.failure_stage` and `outcome.code`; line 2345 exposes `state.stage` as `StepRunReport.failure_stage`. Lines 1819–1822 also use these raw values as the raised error's attribution. The latest safe projection at line 1627 applies only when the unit's own status is not succeeded.

Problem: `validate_unit_result` validates unit/target identity and known unit status, but does not reject a unit marked `succeeded` containing a failed logical member. The successful-unit host branch explicitly accepts terminal member statuses, derives no expected outputs for a failed member, projects the failed member and raises afterward. It therefore reaches the still-raw stage assignment. The same metadata privacy invariant remains violated through this sibling projection branch.

Evidence: Exact admitted Local Fanout with captured concurrency two. The left executor returns `PhysicalUnitResult(status="succeeded", outputs=())` with `PhysicalLogicalOutcome("left", "failed", attempts=1, code="PMADP520", failure_stage='rows=[{"id":"SOL_PRIVATE_ROW_MARKER"}]')`. The host detects failure later and produces a partial report: four succeeded, one failed, one skipped; left sink effects zero; right sink effects one; every started executor is cleaned. The marker nevertheless appears in the recursive public report. The new assertion fails only after all terminal/count/diagnostic/effect/cleanup assertions pass. No real secret or private rows were used.

Relationship to current change: This is the same host failure-metadata projection root as FINAL-009. The latest remediation fixes the earlier branch without fixing the second branch or safely rejecting the inconsistent result before attribution. It is not a new finding ID, a new feature requirement or a cosmetic request for a cleaner implementation.

Why it matters: A malformed provider result must not cause row-bearing metadata to enter persisted/public reports. The host already recognizes the logical failure, so a safe terminal response is practical.

Why this blocks the current change: The supported public executor/report path still violates AC-021's recursive no-row/no-secret/no-native-ref contract. Blocker tests 1, 4 and 6 apply. Correct valid failed-unit behavior alone does not permit disclosure when the host encounters an inconsistent result.

Required behavior: Safely project executor-controlled failure metadata on every reachable logical outcome path, or reject inconsistent unit/member status combinations with safe terminal attribution before any raw failure metadata reaches state/report/error projections. Preserve ordinary `transform` attribution for valid failures, truthful attempts/totals, dependent skips, independent publication, receipts and cleanup. Do not recognize the marker, status permutation or fixture names specially.

Acceptance criteria:

1. The original terminal-outcome and failed-unit privacy cases remain passing.
2. The inconsistent successful-unit/failed-member case reaches a safe terminal failure without the synthetic marker anywhere in `report.to_dict()`; either safe attributed handling or contract-consistent malformed-result rejection is acceptable.
3. Left remains failed/one attempt and left sink skipped/zero effects; right publication succeeds once; all started executors are cleaned and counts remain four succeeded/one failed/one skipped.
4. Both metadata projection paths are inspected; protected verification and related gates pass before source-bound evidence refresh.

Verification artifact: `tests/runtime/test_sol_0_53_contract_rereview.py::test_sol_011_failed_executor_branch_has_terminal_logical_report[final-009-inconsistent-unit-private-stage]`.

Verification status: **FAIL — EXPECTED BLOCKER VERIFICATION**. Final targeted run, including the isolated schema-deadline control: one failed, four passed, 18 deselected, 8.22 seconds. The original two SOL-011 cases, unknown-receipt privacy and schema-deadline case pass. The new case accepts PMADP400 or PMADP520 for malformed-result rejection; the original valid failed-unit cases still require PMADP520. One added case constrains a different reachable host branch, not an equivalent repetition of the first serializer input.

Repeated-failure guidance: **ESCALATION RECOMMENDED** for a complete bounded outcome-projection trace before another remediation. This privacy invariant has required several partial remediations; the latest stage fix again covers only one entry path. Stronger implementation reasoning across both host branches is appropriate. No specification change, broader architecture redesign or unrelated cleanup is required.

### FINAL-008 — Committed 0.53 proof is stale for the reviewed revision

Severity: **Medium**.
Disposition: **BLOCKER**.
Related AC: **AC-024**.

Location: `docs/11_DEVELOPMENT/evidence/adaptive_0_53/qualification.json` and its companion stdout/stderr/JUnit; `scripts/check_adaptive_0_53.py:127–164,243–247`.

Problem: The latest remediation ran a passing campaign to a temporary directory and refreshed historical 0.52 source fingerprints, but did not refresh the committed 0.53 bundle. The default non-writing verifier requires source/environment/scenario/JUnit/hash agreement with that committed bundle. Green CI uses `--write --output` for environment proof, so it does not establish this separate required committed-bundle check.

Evidence before this review's new case: Recomputing `source_revision()` using the committed HEAD bytes of the only modified tracked test yields `sha256:bdcc5c31cf8ab8afe1ece06153612e12bc2fffd6887cfd7d6f4281a9f651a47a`. This exactly matches Luna's passing temporary 119/119 campaign in `/tmp/sol053-fixed-proof/qualification.json`. The committed bundle instead has 118 scenarios, observation time 2026-09-14T11:53:05Z and source `sha256:a98bd18c1d0ba43a47f663b86175603002e737d980bf77a6c37482702aad1d72`. Calling the actual committed-evidence verification function with that honest HEAD campaign returns false. An assertion expecting acceptance fails. Thus the mismatch already existed on the reviewed commit; it is not merely caused by adding this review's third variant.

Relationship to current change: Required phase evidence refresh was omitted after the latest production/test change. Stable FINAL-008 is preserved for the source-bound verification requirement; the verifier's fail-closed implementation remains correct.

Why it matters: Required non-writing release verification cannot reproduce the committed release evidence for the code/test revision being reviewed. A successful temporary/CI run is valuable but does not repair the committed bundle or satisfy its explicit gate.

Why this blocks the current change: AC-024 and the plan's evidence contract explicitly require a passing non-writing evidence gate. Blocker tests 1 and 7 apply. This is a required change-related proof failure, not a request for repository-wide evidence regeneration or stronger future qualification.

Required behavior: After FINAL-009 is fixed and all required campaign cases pass without skips/source mutation, regenerate the committed 0.53 qualification JSON and companions together, retain their safe projections, and run the default non-writing verifier successfully. Refresh any historical source fingerprints that legitimately changed, without modifying verification assertions or disabling gates.

Acceptance criteria:

1. Committed 0.53 source/scenario/count/environment/JUnit/output hashes match an executed passing campaign on the final source/test inputs.
2. `uv run --no-sync python scripts/check_adaptive_0_53.py` exits zero without rewriting proof.
3. Existing stale/tampered/fabricated/skipped-evidence rejection tests still pass; exact-head environment CI remains green.

Verification artifact: Existing `scripts/check_adaptive_0_53.py` in default non-writing mode and its committed-bundle verification gate. No extra failing test or gate bypass is needed.

Verification status: **FAIL — OPEN BLOCKER**, independently isolated on committed HEAD inputs. Fresh command result is recorded below. Fixing proof is dependent on the privacy production fix; do not regenerate a passing claim for the current failing case.

## Quality gates and verification audit

| Gate | Executed | Result / classification |
|---|---|---|
| Original protected review suites | Local, before addition | PASS — 42 passed, one warning, 36.49 seconds. |
| Expanded targeted FINAL-009/SOL-011 | Local | Three pass; one EXPECTED BLOCKER VERIFICATION failure. |
| Final expanded 0.53 temporary campaign | Local, isolated | 120 executed, 119 pass, no skips, source_changed=false; only the expected FINAL-009 privacy failure. |
| Initial expanded campaign under concurrent load | Local | 120 executed, 118 pass, no skips, source_changed=false; expected privacy failure plus schema-delay exercise timing failure, resolved on isolated repeat. |
| Default non-writing 0.53 verifier | Local | FAIL — OPEN BLOCKER; reports committed evidence missing/stale/skipped/unsubstantiated. Committed-HEAD inputs independently isolate stale proof. |
| Configured core marker suite | Local | 1,854 passed, five existing skips, 403 deselected, 48 warnings; one historical evidence fingerprint failure caused by the new review test, 174.95 seconds. |
| Optional dataframe/compiler/conformance | Local | PASS — 62 passed, 194 deselected, 8.92 seconds. |
| Ruff / format / configured Pyright | Local, after addition | PASS — 947 files formatted; zero errors/warnings. |
| Docs consistency / strict build | Local | PASS — strict build 24.57 seconds to temporary directory. |
| Surface / diagnostics / protocol / manifests / security / release | Local | PASS — six existing gates. |
| Core sdist / wheel / isolated optional-free import | Local | PASS — 0.52.1 build and core/physical protocol import without Polars/Pandas/PyArrow. |
| Exact-head CI | Independently retrieved | PASS — run 34845463617, head 1b48168b, all 37 jobs successful; predates new review verification. |

The schema-deadline campaign exercise failed on `entered == []`: the 0.1-second member limit expired before the delayed schema operation was reached under concurrent campaign/core load. This same protected test passes in the fresh original suite, the reviewed CI matrix and the isolated repeat above. No assertion or production code is changed to accommodate it. Do not call the initial expanded campaign wholly green or misclassify this as the expected privacy failure. A final campaign after formatting the verification fixture is recorded below.

Final proof: `/tmp/sol053-1b48168b-final-proof/qualification.json`, source `sha256:8aa2217334e91ffa4bba4d9c239a2618a8b0c9476c885d465ecc69e7eab61ce9`. All 120 required cases executed; 119 passed and only the inconsistent-unit privacy case failed. This is temporary honest failing verification, not a rewritten committed release claim. An earlier campaign started before final fixture formatting was interrupted and is not counted as completed evidence.

The suite was challenged at the sibling successful-unit outcome projection and at the distinction between environment proof and committed non-writing proof. Existing assertions and direct serializer checks were honest, but covered only the first failure branch. Current CI is honest, but its `--write --output` step does not verify the committed default bundle. No tests/gates were weakened, and no failing proof was refreshed on the release branch.

## Follow-ups and observations

| Finding | Severity | GitHub |
|---|---|---|
| SOL-012 — Pre-existing medallantic migration fingerprint golden discrepancies | Low | EXISTING ISSUE #145 — https://github.com/eddiethedean/etlantic/issues/145 (open). Baseline/current evidence remains in the prior review and issue; outside this remediation. |

New FOLLOW-UPs: none. Existing planning/docs tracking #83/#86 remains separate. Observations requiring remediation: none.

## Convergence

- Latest previous blocker fully resolved: zero; FINAL-009 is partially fixed with concrete evidence of the second path.
- Historical blocker IDs VERIFIED FIXED: nine; FINAL-008 and FINAL-009 remain bounded blockers.
- Blockers remaining: two, FINAL-009 and FINAL-008.
- New findings attributable to latest remediation: one omitted proof refresh, under existing FINAL-008; no new production root ID.
- New follow-ups discovered: zero.
- SOL-011 terminal failure retention remains closed. Both remaining items concern existing scope: safe failure attribution followed by complete source-bound proof refresh. The loop is not yet converged, but no feature or architecture expansion is required.

Only **FINAL-009** and **FINAL-008** enter Luna/Terra remediation, in that dependency order. Preserve all protected verification, receipt/artifact/cleanup behavior and independent branch semantics. Normal Sol PASS is required before another final release check.

**NEEDS FIXES**
