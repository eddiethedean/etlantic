# Sol production re-review — phase 0.53

Reviewed production: `a5ae2ae39b26c0fc1dc8ec494ade3552005817f1`.
Verdict: **NEEDS FIXES**.

## Contract and scope integrity

Authority remains `docs/11_DEVELOPMENT/IMPLEMENTATION_PLAN_0_53.md`, REQUIRED BEHAVIOR, AC-001–AC-024, verification matrix and explicit non-scope. Read the current pasted request, approved plan, original review, latest Sol re-review and Luna remediation reports; inspected the production diff, admission, support matcher, stored-plan host, physical scheduling, result attribution, boundary operations, publication, artifact lifecycle, public protocol projections, tests, docs, packaging and CI gates.

The change remains Experimental, fixture-qualified static local `/2` execution for Local, Polars, Pandas and both single-cut Arrow directions. Whole-DAG admission, exact pinned adapters, stored physical dependencies, publication-only commits, resource fencing, safe metadata and independent/default `/1` compatibility are required. SQL/Spark adaptive execution, durable/control-plane acceptance, arbitrary topology/fusion qualification, producer-skipping caches, medallantic migration repair and 0.54 availability graduation remain outside scope.

The latest production changes use `PhysicalLogicalOutcome.to_dict()` in both host outcome branches. Evidence was refreshed after the prior third protected case. No additional dependency, public API, migration or unrelated production refactoring appears in that remediation. The host branch omission was addressed, but its shared serializer still cannot establish the failure-stage privacy invariant.

This review adds one parameterized case to an existing protected test and this report. Production, previous assertions/cases, configuration and committed evidence remain unchanged.

## Acceptance criteria

Fresh default non-writing qualification ran on the clean committed HEAD before the new verification case: 120 executed, 120 passed, no skips, `source_changed=false`. It accepted the committed evidence. The expanded protected suites subsequently ran in isolation: 43 passed and only the new privacy case failed.

| AC | Status | Evidence |
|---|---|---|
| AC-001 | VERIFIED | Explicit/default identity, no-adaptive controls, core regressions and exact-head compatibility CI pass; independent `/1` dispatch inspected. |
| AC-002 | VERIFIED | Real five-family stored differentials, public entry tests, exact single-target branches and directional ports pass; support matcher inspected. |
| AC-003 | VERIFIED | Planning input capture, stored portable descriptor/partial execution, historical and marker/envelope rejection tests pass; immutable admission checks inspected. |
| AC-004 | VERIFIED | All-unit support analysis and live storage/mode rejection tests pass before session/effects; complete admission precedes physical execution. |
| AC-005 | VERIFIED | Executor replacement after admission remains unused; live identity/version/capability/allowlist/binding/contract/evidence checks and per-run pins inspected; denial controls pass. |
| AC-006 | VERIFIED | Exact unit/target result validation, metadata-only analysis and explicit executor compatibility controls pass. |
| AC-007 | VERIFIED | Request-only/default/stored/source-only/partial scope and no-widening controls pass; stored request comparison inspected. |
| AC-008 | VERIFIED | Transitive no-start controls pass; failing branch publication is suppressed while independent publication succeeds in every returned-outcome probe. Stored edges remain scheduling authority. |
| AC-009 | VERIFIED | Numeric policy rejection, Profile/request precedence and captured bounded ready-loop controls pass. |
| AC-010 | VERIFIED | Real empty/nullable five-family differentials and portable target/prepare controls pass; native selection remains rejected. |
| AC-011 | VERIFIED | Both real Arrow directions, distinct routes, one transfer conversion and native transfer deadline fencing tests pass. |
| AC-012 | VERIFIED | Real collection shape/bounds tests pass across the qualified families; closed operation descriptor checks inspected. |
| AC-013 | VERIFIED | Real validation and post-compile schema deadline controls pass; failed barriers do not publish. |
| AC-014 | VERIFIED | Checkpoint/reuse execution, retention validation, malformed timestamps and staged checkpoint rollback/deadline controls pass. |
| AC-015 | VERIFIED | Member attempt/timeout/private prefix fencing and unsafe retry admission controls pass; no timeout retry introduced. |
| AC-016 | VERIFIED | All returned-outcome probes retain one terminal report per selected node, truthful attempts/totals, downstream skips and independent right publication. |
| AC-017 | VERIFIED | Native drain/abandon/queued cancellation, member/run/boundary deadlines, checkpoint registration fencing and cancel/cleanup controls pass in both fresh campaigns. |
| AC-018 | VERIFIED | Memory/JSON/CSV publication, public file receipt, no-write, late known receipt and destination locking controls pass; only publication commits. |
| AC-019 | VERIFIED | Ack loss, committed/unknown deadline receipts, reconciliation obligations and explicit writer compatibility controls pass. |
| AC-020 | VERIFIED | Physical/logical provenance and differential totals pass. New failing privacy probe reaches the final assertion after correct terminal counts and diagnostic attribution. |
| AC-021 | NOT SATISFIED | Identifier-shaped provider stage data remains unchanged in the protocol projection and enters the public report. FINAL-009. Namespaced/migration controls otherwise pass. |
| AC-022 | VERIFIED | Unsupported consumers, modes, targets and durable/dynamic paths retain pre-effect rejection; docs describe Experimental local qualification. |
| AC-023 | VERIFIED | Concurrent same-runtime isolation, owned/shared/borrowed lifetime and repeatable cleanup/owner obligation controls pass. All executors started in the new probe are cleaned. |
| AC-024 | PARTIALLY SATISFIED | Committed HEAD's required non-writing evidence, real campaign, wheel, docs and exact-head CI pass. Newly demonstrated in-scope privacy behavior fails protected verification; passing source-bound proof must follow remediation. |

## Previous blockers

| Finding | Status | Verification |
|---|---|---|
| FINAL-001 | VERIFIED FIXED | Whole-DAG/all-unit/storage denial and post-admission executor replacement controls pass; exact adapter pins inspected. |
| FINAL-002 | VERIFIED FIXED | Exact required diamond/fanout, directional ports and named support matcher controls pass. |
| FINAL-003 | VERIFIED FIXED | Actual transfer, truthy no-op descriptor rejection, collection/checkpoint/reuse and retention controls pass. |
| FINAL-004 | VERIFIED FIXED | Effective/default/stored portable request, source-only selection, partial scope and captured concurrency controls pass. |
| FINAL-005 | VERIFIED FIXED | Real publication failure, ack loss, late known receipts, unknown obligations and explicit writer controls pass. |
| FINAL-006 | VERIFIED FIXED | Concurrent default runs isolate logical artifacts; per-run physical host state inspected. |
| FINAL-007 | VERIFIED FIXED | Fresh member/run/schema/boundary fencing and drain/cleanup tests pass. No timing failure occurred in this review's completed campaigns. |
| FINAL-008 | VERIFIED FIXED | Default non-writing gate exits zero on clean committed HEAD: 120/120 scenarios, matching source/bundle and unchanged source; historical 0.52 evidence also passes. Tampered/fabricated/skipped-proof rejection controls pass. |
| FINAL-009 | PARTIALLY FIXED | Both host branches now call the projection; all three previous cases pass. New identifier-shaped stage case fails the same privacy invariant. |
| SOL-010 | VERIFIED FIXED | Fresh docs consistency and strict MkDocs build pass. |
| SOL-011 | VERIFIED FIXED | Failed-member terminal retention, attempts/totals, independent publication and cleanup assertions pass before the privacy assertion, including the new valid failed-unit result. |

## Remaining blocker

### FINAL-009 — Identifier-shaped failure stages still disclose provider data

Severity: **High**.
Disposition: **BLOCKER**.
Related AC: **AC-021**, consequential **AC-024**.

Location: `src/etlantic/runtime/physical_protocol.py:94–105` (`_identifier`), line 308 (`PhysicalLogicalOutcome.to_dict`), line 387 (`PhysicalUnitFailure.to_dict`); `src/etlantic/runtime/orchestrator.py:1626–1632,1789–1807,2349`.

Problem: The host now uses the serializer on both branches, but `failure_stage` is projected as a general lexical identifier. Any string of at most 256 characters matching `[A-Za-z0-9_.:/-]+` is returned unchanged. Matching a character class does not establish that provider-controlled failure text is metadata. Simple row values or secret text can match this class. Stage summaries share the same helper.

Evidence: Without editing the repository, calling `PhysicalLogicalOutcome("left", "failed", code="PMADP520", failure_stage="rows:SOL_PRIVATE_ROW_MARKER").to_dict()` returns that stage unchanged. Running the existing supported Local Fanout executor/report probe with this stage fails the final recursive public report assertion. Both a valid failed-unit result and the existing inconsistent-success-unit path reproduce it; the added automated case uses the valid failed-unit result so the finding does not depend on malformed unit status.

The exact-authorized provider returns a failed left member with one attempt and PMADP520. Real LocalScheduler execution produces a partial terminal report: four succeeded, one failed, one skipped; left publication has zero effects; right memory publication happens once; every started executor is cleaned. All those assertions pass. `SOL_PRIVATE_ROW_MARKER` nevertheless appears in `json.dumps(report.to_dict())`, and the existing privacy assertion fails. Only synthetic text was used, never actual private rows or secrets.

Relationship to current change: This is the same returned failure-metadata privacy root as FINAL-009. The branch bypass is fixed, but the remediation assumes the existing projection is semantically safe. The new case exposes a different input class admitted by its predicate. It is not an unrelated repository defect, a new feature or a request to sandbox authorized code.

Why it matters: A provider can unintentionally place data-bearing text in error attribution. Public/persistable run reports then disclose it despite the explicit safe failure contract. Ordinary identifier-shaped data is a plausible failure input; braces, quotes and whitespace are not necessary for sensitive text.

Why this blocks the current change: The supported changed executor/report path violates AC-021's recursive exclusion of rows/resolved secrets/native data. Blocker tests 1, 4 and 6 apply. The host can preserve terminal failure safely without disclosing unrestricted stage text; accepting a syntactically identifier-shaped payload does not satisfy the release contract.

Required behavior: Failure stages must be semantically constrained safe metadata across logical-outcome and failure-summary projections. Preserve established stage attribution such as `transform`; safely redact/hash unknown provider stage text or reject it with safe terminal attribution. Character filtering alone is insufficient. Preserve truthful attempts/totals, downstream skips, independent publication, receipt retention and cleanup; keep stored provenance and reconciliation identifiers compatible. No marker, fixture or status special-case is acceptable.

Acceptance criteria for resolution:

1. The new valid failed-unit/identifier-shaped stage case passes with no synthetic marker anywhere in the recursive public report.
2. All three previous returned-outcome cases pass, including ordinary `transform` attribution and both failed-unit and inconsistent successful-unit paths.
3. Left remains failed with one attempt, left sink skipped with zero effects, right sink succeeds exactly once, all six logical reports remain terminal with four succeeded/one failed/one skipped, and all started executors are cleaned.
4. The shared failure-stage projection is inspected at the protocol and host entry points; unknown stage text receives a safe semantic projection independently of punctuation. Protected verification and relevant gates pass before source-bound evidence refresh.

Verification artifact: `tests/runtime/test_sol_0_53_contract_rereview.py::test_sol_011_failed_executor_branch_has_terminal_logical_report[final-009-identifier-shaped-private-stage]`.

Verification status: **FAIL — EXPECTED BLOCKER VERIFICATION**. Expanded protected suites: one failed, 43 passed, one warning, 28.92 seconds. The only failing case is the new stage class, at the recursive privacy assertion. Log: `/tmp/sol053-a5ae2ae3-protected.log`; JUnit: `/tmp/sol053-a5ae2ae3-protected.xml`.

Repeated-failure guidance: **ESCALATION RECOMMENDED** for stronger bounded implementation reasoning about field semantics and all failure-stage projections. Multiple prior repairs addressed serializer bypasses without establishing the shared privacy invariant. The approved requirement is unambiguous; no scope expansion or subsystem redesign is requested.

### Source-bound evidence after this review

FINAL-008 is genuinely fixed on the reviewed committed HEAD. Before the verification addition, the default gate accepted source `sha256:9821cc94f32bde6611414fb1c5566ed373f84ffeb5a915b540fc7842bf1733f6`, all 120 executed/passing cases, and the committed companion hashes. Its full fresh record is `/tmp/sol053-a5ae2ae3-nonwriting.log`.

The single new protected case changes the source digest and future campaign inventory. Refresh the dependent 0.53 bundle and legitimate historical fingerprints only after the production privacy fix and passing verification. This review does not reopen FINAL-008 merely because its own verification changes hashed inputs; it does not rewrite a passing release claim for the failing case.

## Quality gates and verification audit

| Gate | Executed | Result / scope |
|---|---|---|
| Default non-writing adaptive 0.53 verifier | Fresh local, clean committed HEAD | PASS — 120 executed, 120 passed, no skips, unchanged source and accepted committed proof. |
| Historical adaptive 0.52 verifier | Fresh local, before verification addition | PASS — 10 artifacts, 18 acceptance criteria. |
| Configured core marker suite | Fresh local, before verification addition | PASS — 1855 passed, 5 existing skips, 403 deselected, 48 warnings, 184.69 seconds. |
| Expanded protected Sol suites | Fresh local, after addition | EXPECTED BLOCKER VERIFICATION — one failure (FINAL-009), 43 passed, one warning, 28.92 seconds. |
| Optional dataframe/compiler/public conformance | Fresh local | PASS — 62 passed, 194 deselected, 8.66 seconds. |
| Ruff / format / configured Pyright | Fresh local on HEAD | PASS — 947 files formatted; zero type errors/warnings. |
| Added verification fixture Ruff / format | Fresh local, after addition | PASS — one file; no ignores or configuration changes. |
| Docs consistency / strict build | Fresh local | PASS — strict site built to `/tmp/sol053-a5ae2ae3-docs`, 31.75 seconds. |
| Surface / diagnostics / protocol / manifests / security / release / agent guidance | Fresh local | PASS — all seven existing commands. Release gate confirms in-repo 0.52.1 metadata; it does not grant this review's PASS. |
| Stable foundation / portable 0.50 evidence | Fresh local | PASS — 21 foundation tests and structurally complete legacy evidence. |
| Core sdist / wheel | Fresh local | PASS — artifacts in `/tmp/sol053-a5ae2ae3-dist`. |
| Isolated optional-free wheel import | Fresh local | PASS — public core/physical API imports and simple wire projection with Polars, Pandas and PyArrow absent. |
| Exact-head CI | Independently retrieved, not locally rerun | PASS — run 34850722891, exact a5ae2ae3 head, all 37 jobs successful; predates the added review case. |

No completed gate produced a change-caused failure other than the confirmed privacy requirement. The full campaign was not redundantly rerun after the verification-only addition: the fresh complete HEAD campaign and expanded isolated protected suites provide the original release evidence and the bounded failing regression respectively. The future expanded inventory has not been claimed passing.

How could the change still be wrong with every current HEAD test green? The previous privacy cases use JSON-like punctuation, which the general identifier helper hashes. None exercised data-bearing text inside its accepted lexical class. Both host branches and CI can therefore pass while sharing this incorrect safety assumption. The new case constrains the underlying semantic exclusion while exercising actual admission, scheduling, terminal reports, independent memory publication and cleanup. No mock bypasses those host paths, no assertion was weakened, and no gate was disabled.

## Follow-ups and observations

| Finding | Severity | GitHub |
|---|---|---|
| SOL-012 — Pre-existing medallantic migration fingerprint golden discrepancies | Low | EXISTING ISSUE #145 — https://github.com/eddiethedean/etlantic/issues/145, independently confirmed open. Outside the approved boundary and this privacy remediation. |

New follow-ups: none. Observations requiring remediation: none. Existing planning/docs tracking #83/#86 stays separate.

## Convergence

- Previous blockers newly resolved: one, FINAL-008.
- Total stable historical findings VERIFIED FIXED: ten.
- Blockers remaining: one, FINAL-009, PARTIALLY FIXED.
- New blocker IDs or regressions attributable to remediation: zero; the remaining defect is the existing shared privacy root.
- New follow-ups discovered: zero.
- The remediation set shrank from two to one. Terminal outcome retention and both host projection entry paths remain corrected. The loop needs a semantic failure-stage fix rather than another branch-specific patch.

Only **FINAL-009** enters Luna/Terra remediation, followed by its dependent source-bound evidence refresh. FOLLOW-UPs and observations are excluded. Normal independent Sol PASS is required before final release checking.

**NEEDS FIXES**
