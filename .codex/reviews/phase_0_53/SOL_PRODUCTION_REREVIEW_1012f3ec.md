# Sol production re-review — phase 0.53

Reviewed commit: `1012f3ec76221911e836c254e29f3b06fe064e6b`.

## Contract and scope integrity

Authority remains `docs/11_DEVELOPMENT/IMPLEMENTATION_PLAN_0_53.md`, its REQUIRED BEHAVIOR, AC-001–AC-024, verification matrix and explicit non-scope. Read the current pasted review request, approved contract, previous Sol re-review and Luna resolution; inspected the latest production/verification/evidence diff, shared protocol projection, both host outcome branches, result validation, physical host, admission pins, protected assertions, qualification checker, documentation, packaging and CI configuration.

The release boundary remains Experimental, fixture-qualified static local `/2` execution for Local, Polars, Pandas and both single-cut Arrow directions. Whole-DAG admission, exact pinned adapters, stored dependencies, publication-only commits, safe metadata, lifetime fencing and independent/default `/1` compatibility remain required. SQL/Spark adaptive execution, durable/control-plane acceptance, arbitrary topology/fusion qualification, producer-skipping caches, unrelated medallantic migration repair and 0.54 graduation remain outside scope.

The latest production remediation changes only `physical_protocol.py`. The shared failure-stage serializer now preserves a finite runtime vocabulary and hashes every unknown string regardless of punctuation. Both logical outcomes and physical failure summaries use it; both host outcome branches already consume the logical projection. Exact stored identities, receipt formats, supported dependency ranges, public signatures and persistence formats remain unchanged. The protected regression was added by the previous Sol review; its original assertions and three sibling cases remain intact. Evidence companions and historical fingerprints were refreshed for the changed source/inventory. No gate was weakened or discovery exclusion added.

This review adds only this review artifact. It does not modify production, tests, configuration or committed qualification evidence.

## Acceptance criteria

Fresh default **non-writing** qualification on the clean reviewed commit passed: **121 executed, 121 passed, no skips**, `source_changed=false`. The verifier accepted the committed companion hashes and source revision `sha256:6aaaa08cadd74d6817d912c72f78e0ecfa340104f3eb72cc334aa51cc8f4e642`. Local environment: macOS arm64, Python 3.11.15, Polars 1.42.1, Pandas 2.3.3, PyArrow 25.0.0, development-base core/plugins 0.52.1. The inventory includes 44 protected Sol cases, 50 physical qualification cases, 14 native execution cases, seven adaptive entry cases and six adaptive planner cases.

| AC | Status | Evidence |
|---|---|---|
| AC-001 | VERIFIED | Explicit/default identity and no-adaptive controls, independent `/1` dispatch, foundation compatibility and exact-head CI pass. |
| AC-002 | VERIFIED | Real five-family stored differentials, public entries, exact branch families and directional ports pass; exact support remains closed. |
| AC-003 | VERIFIED | Effective input capture, stored portable descriptors, historical wire and marker/envelope tamper controls pass. |
| AC-004 | VERIFIED | Whole-DAG/all-unit analysis, live storage and write-mode denial controls pass before session/effects; admission ordering remains intact. |
| AC-005 | VERIFIED | Post-admission replacement stays unused; exact live identity/version/allowlist/binding/contract/evidence checks and per-run pins remain enforced. |
| AC-006 | VERIFIED | Metadata-only analysis, unit/target result identity and explicit executor compatibility controls pass. |
| AC-007 | VERIFIED | Request-only/default/stored/source-only/partial scope, captured inputs and no-widening controls pass. |
| AC-008 | VERIFIED | Transitive no-start controls pass; failed dependencies suppress downstream publication while the independent branch publishes once. Stored physical edges remain authority. |
| AC-009 | VERIFIED | Numeric policy rejection, Profile/request precedence and captured bounded concurrency controls pass. |
| AC-010 | VERIFIED | Real typed-empty/nullable differentials and portable/source/sink preparation controls pass; native selection remains rejected. |
| AC-011 | VERIFIED | Both real Arrow directions, distinct port routes, one transfer conversion and native transfer fencing controls pass. |
| AC-012 | VERIFIED | Actual finite collection shape/bounds pass across qualified families; unqualified policies remain rejected. |
| AC-013 | VERIFIED | Actual validation and post-compile schema deadline controls pass; failed barriers do not publish. |
| AC-014 | VERIFIED | Checkpoint/reuse, retention, malformed timestamps and partial checkpoint rollback/deadline controls pass. |
| AC-015 | VERIFIED | Member attempts, private-prefix retention, safe/unsafe retry and timeout fencing controls pass; timeout does not retry. |
| AC-016 | VERIFIED | All four returned-outcome cases retain six terminal logical reports, truthful attempts/totals, downstream skips and independent publication. |
| AC-017 | VERIFIED | Native drain/abandon/queued cancellation, member/run/boundary deadlines, checkpoint registration fencing and cleanup controls pass. |
| AC-018 | VERIFIED | Memory/JSON/CSV publication, file receipts, no-write, known late receipts and destination locking controls pass; publication-only commit ordering remains intact. |
| AC-019 | VERIFIED | Ack loss, committed/unknown deadline receipts, reconciliation obligations and explicit writer compatibility controls pass. |
| AC-020 | VERIFIED | Physical/logical provenance and differential totals pass; the repaired privacy probe preserves attribution and terminal counts. |
| AC-021 | VERIFIED | Closed semantic stage projection passes both protocol surfaces and both actual host branches; recursive marker/native-receipt and namespaced/migration controls pass. |
| AC-022 | VERIFIED | Unsupported consumers/modes/targets and durable/dynamic paths retain pre-effect rejection; docs state Experimental local qualification. |
| AC-023 | VERIFIED | Concurrent same-runtime isolation, shared/owned/borrowed lifetime, repeatable cleanup and owner-obligation controls pass. All started executors in the returned-outcome probes are cleaned. |
| AC-024 | VERIFIED | Fresh source-bound real campaign, historical evidence, public smoke, strict docs, core build, isolated optional-free imports and exact-head multi-platform CI pass. |

## Previous blockers

| Finding | Status | Verification |
|---|---|---|
| FINAL-001 | VERIFIED FIXED | Whole-DAG/all-unit/storage denial and post-admission replacement controls pass; exact pins retained. |
| FINAL-002 | VERIFIED FIXED | Required exact diamond/fanout, directional port and support matcher controls pass. |
| FINAL-003 | VERIFIED FIXED | Real handoff, no-op rejection, collection/checkpoint/reuse and retention controls pass. |
| FINAL-004 | VERIFIED FIXED | Effective/default/stored portable request, source-only/partial scope and captured concurrency controls pass. |
| FINAL-005 | VERIFIED FIXED | Publication failure, ack loss, late known receipts, unknown obligations and explicit writer compatibility pass. |
| FINAL-006 | VERIFIED FIXED | Concurrent default runs isolate logical artifacts; remediation adds no shared mutable state. |
| FINAL-007 | VERIFIED FIXED | Fresh member/run/schema/boundary fencing, native drain and cleanup controls pass. |
| FINAL-008 | VERIFIED FIXED | Default non-writing verifier accepts current committed proof, 121/121 executed/passing cases, exact source and companion hashes; tampered/fabricated/skipped evidence controls pass. |
| FINAL-009 | VERIFIED FIXED | Previously failing identifier-shaped stage and all three siblings pass in the actual admitted executor/report path. Both failure serializers preserve known stages and hash unknown text. |
| SOL-010 | VERIFIED FIXED | Fresh docs consistency and strict MkDocs build pass. |
| SOL-011 | VERIFIED FIXED | Every returned-outcome probe preserves failed-member attempts/totals, downstream skips, independent publication and cleanup. |

## FINAL-009 root-cause verification

The prior helper preserved arbitrary short lexical identifiers, including data-bearing stage strings. The new `_failure_stage()` uses a semantic allowlist; unknown strings are directly hashed rather than routed through the permissive identity helper. Both `PhysicalLogicalOutcome.to_dict()` and `PhysicalUnitFailure.to_dict()` use it. Both outcome-processing host branches consume the safe projection before state/report attribution. No fixture marker or unit-status special-case exists.

The previously failing valid failed-unit case now passes with `rows:SOL_PRIVATE_ROW_MARKER` absent from the entire recursive public report. Its sibling JSON-shaped cases also pass for failed-unit and inconsistent successful-unit results. Ordinary `transform` remains readable. All four cases retain four succeeded/one failed/one skipped logical nodes, the failed member's one attempt, zero left publication, exactly one right publication, a meaningful failure diagnostic and cleanup of every started executor.

Additional read-only runtime probes checked all nine `FailureStage` values plus `execute`/`admission`, confirming compatibility in the logical serializer. Unknown identifier-shaped, slash-shaped, JSON-shaped and empty strings, `None` and an opaque object receive identical safe projections on both failure surfaces. These probes use synthetic text only. The fix preserves trusted provenance and reconciliation identifiers rather than applying a breaking blanket transformation to them.

## Verification audit and fresh challenge

How could this change remain wrong while tests pass? A serializer-only assertion could miss a host bypass, malformed unit status could avoid the normal failed-unit path, or a stale bundle could omit the newly demonstrated input class. The retained four-case host regression exercises both outcome branches, actual admission, stored scheduling, terminal reports, real independent memory publication and cleanup. The default non-writing campaign independently executed and included all four identities, including the new valid failed-unit case, then accepted current source-bound evidence. Direct physical-failure serialization probes cover the second shared entry point. The closed vocabulary covers unknown strings by semantics rather than enumerating known reproducers.

Reviewed verification changes contain only the previous Sol case addition; no assertion weakening, expected failure, skip, broad mock, gate disabling or test-discovery change appears. The admitted executor is deliberately controlled for failure injection, while production admission, scheduler, reporting and memory publication remain exercised. Real backend differentials/boundaries remain part of the same fresh campaign. No additional failing artifacts are needed because no blocker remains.

## Quality gates

All local commands below were executed during this review. Exact-head CI was independently retrieved, not locally rerun. Detailed local outputs are retained under `/tmp/sol053-1012-*`.

| Gate | Executed | Result |
|---|---|---|
| `check_adaptive_0_53.py` default non-writing verifier | Fresh local, clean reviewed commit | PASS — 121/121, no skips, unchanged source; committed proof accepted. Log `/tmp/sol053-1012-evidence.log`. |
| Protected Sol suites | Within fresh full campaign | PASS — 44/44 executed cases, including all four returned-outcome cases. |
| Physical qualification suite | Within fresh full campaign | PASS — 50/50 executed cases. |
| Configured core marker suite | Fresh local | PASS — 1,855 passed, five existing skips, 404 deselected, 48 warnings, 179.71 seconds. Log `/tmp/sol053-1012-core.log`. No skips occur in the required adaptive qualification campaign. |
| `check_adaptive_0_52.py` | Fresh local, non-writing | PASS — 10 artifacts, 18 acceptance criteria. |
| Ruff / format / configured Pyright | Fresh local | PASS — 947 files formatted, zero type errors/warnings. |
| Surface / diagnostics / protocol / manifests / security / release / agent guidance | Fresh local | PASS — all seven existing commands. Release gate validates development-base metadata; it does not grant review approval. |
| Stable foundation | Fresh local | PASS — 21 passed, one existing namespace warning. |
| Portable 0.50 evidence | Fresh local | PASS — complete, structurally valid legacy evidence. |
| Docs consistency / strict build | Fresh local | PASS — strict site built to `/tmp/sol053-1012-docs`, 25.95 seconds. |
| Core sdist / wheel | Fresh local | PASS — artifacts in `/tmp/sol053-1012-dist`. |
| Isolated optional-free wheel import | Fresh local | PASS — public core/physical imports and failure projections with Polars/Pandas/PyArrow absent. |
| Exact-head CI | Independently retrieved | PASS — run [34862328464](https://github.com/eddiethedean/etlantic/actions/runs/34862328464), exact reviewed head, all 37 jobs successful. Includes Linux/macOS/Windows Python 3.11–3.13 qualification and optional compatibility jobs. |
| Diff whitespace check | Fresh local | PASS. |

## New blockers

None.

## Follow-ups and observations

| Finding | Severity | GitHub |
|---|---|---|
| SOL-012 — Pre-existing medallantic migration fingerprint golden discrepancies | Low | EXISTING ISSUE [#145](https://github.com/eddiethedean/etlantic/issues/145), independently confirmed OPEN. Outside the approved boundary and this remediation. |

New follow-ups: none. Observations requiring remediation: none. Existing planning follow-ups #83/#86 remain separate. No FOLLOW-UP or observation enters the remediation loop.

## Convergence

- Previous blockers newly resolved: one, FINAL-009.
- Total historical blockers VERIFIED FIXED: eleven.
- Blockers remaining: zero.
- New blockers attributable to remediation: zero.
- New follow-ups discovered: zero.
- The bounded remediation loop has converged; no further implementation work is required by this review.

No completed gate has a change-caused failure. The pre-existing out-of-scope follow-up does not prevent this change from satisfying its contract. A separate Independent Final Release Check remains the next approval step.

**PASS**
