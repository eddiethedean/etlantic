# Sol Production Re-review — Phase 0.53 fallback remediation

Verdict: **PASS** for the current staged working tree, based on independent
execution and inspection below. HEAD remains
`5100e9c4a4fdfcb1d5304e1112590d02b881910e`; this verdict includes the staged
remediation and must not be mistaken for approval of that unchanged HEAD.
Adaptive source revision:
`sha256:6188a6ed1a11deae7eb65ddb69e86870dce71aef903b60543b73918eef87289c`.

Production, tests, documentation, configuration and committed evidence were not
modified by this review. This report is the only new review artifact. No new
failing verification is necessary because no release blocker was found.

## Contract and scope integrity

Authority: `docs/11_DEVELOPMENT/IMPLEMENTATION_PLAN_0_53.md`, its change boundary,
24 ACs and verification matrix, ADR-025, the preceding Sol re-review of
`5100e9c4`, and Luna's `LUNA_FINAL_004_FALLBACK_RESOLUTION.md`. The original
contract remains local static-batch fixture-qualified Experimental `/2`
execution across the five required families, atomic admission and exact stored
dispatch, with explicit `/1` compatibility. An opted-in planning-time fallback
independently produces `/1`; a stored `/2` cannot downgrade. Broader engines,
durable/remote/dynamic execution, native `/2` eligibility and repository cleanup
remain outside scope.

The staged remediation changes only the native implementation resolver, one API
documentation paragraph, two focused tests and generated source metadata. The
Sol-authored fallback reproducer is preserved unchanged. Other protected tests,
public signatures, runtime/dependency ranges, schemas, migrations, CI and test
discovery configuration are unchanged. Historical JSON artifacts differ only
in `repository_revision`; qualification JSON differs only in `source_revision`
and `observed_at`. Scenario identities/results and observation digests were not
weakened.

## FINAL-004 — VERIFIED FIXED

Related AC: AC-001; earlier AC-003/AC-007 effective-input contracts remain
satisfied.

Location: `src/etlantic/runtime/orchestrator.py:3959`,
`LocalOrchestrator._resolve_implementation`; existing fallback generation at
`src/etlantic/planning/adaptive.py:2307` and scheduler dispatch at
`src/etlantic/runtime/scheduler.py:245`.

Root-cause inspection confirms three request origins have distinct contracts:

1. Ordinary explicit native requests contain engine literals. With no fallback
   record and physical mode disabled, their existing late override expression
   remains unchanged.
2. Independent explicit fallbacks originate from adaptive target literals. The
   existing versioned `etlantic.adaptive_fallback` record identifies that
   origin. Their already resolved implementation engine remains authoritative.
3. Physical execution retains admitted descriptor authority. LocalScheduler
   still admits actual `/2` plans before creating the physical host, and its
   physical-mode guard remains authoritative regardless of request literals.

The fix recognizes the existing mapping/schema record instead of guessing
whether a string resembles an installed engine. It preserves the request
object for reporting. Mapping-based detection works with serialized/frozen
metadata and requires no new public mode flag. Callable resolution, portable
compilation, plugin dispatch, scheduling, ownership and publication are not
redesigned.

Fresh verification:

- The unchanged protected fallback reproducer plans target `qualified` as
  engine `local`, executes via LocalScheduler, reports success and publishes ID
  1. The prior target-as-engine failure is gone.
- Ordinary explicit request engine `null` still publishes ID 2.
- The new implementation-side collision test maps target ID `null` to engine
  `local`, serializes/deserializes with fingerprint verification, then executes
  through the shared host. It publishes ID 1 and preserves the original
  request. This proves the fix also prevents silent selection of a valid wrong
  engine, beyond the original unknown-engine failure.
- Original target precedence, unknown-target rejection, required parameters,
  stored input/scope, admitted pins, concurrency and adjacent physical
  contracts pass.

The complete targeted run passed **59 tests, 3 warnings, 32.70s**. The current
core suite includes both fallback artifacts and passed **1865 tests**. The
previous escalation recommendation is no longer active: the missing origin
distinction is now addressed at the shared resolver boundary, and no remaining
verification conflict or architecture escalation was established.

## Acceptance Criteria

Each status is based on fresh execution plus inspection of the corresponding
production path and existing verification. The qualified physical paths remain
unchanged by this native fallback repair; no additional qualification claim is
introduced.

| AC | Status | Evidence |
|---|---|---|
| AC-001 | VERIFIED | Protected ordinary explicit and independent fallback controls pass, including serialized target/engine collision; core compatibility and historical canonical evidence pass. |
| AC-002 | VERIFIED | Five-family real differentials, class/definition/stored execution, named topology/port and unsupported support-row controls pass. |
| AC-003 | VERIFIED | Effective-input and stored descriptor/definition tests, historical wire and recomputed marker/envelope tamper controls pass. |
| AC-004 | VERIFIED | Whole-DAG/last-dependency support and binding admission tests prove zero-effect rejection. |
| AC-005 | VERIFIED | Exact live authorization/storage/binding/version drift and post-admission replacement pin controls pass. |
| AC-006 | VERIFIED | Protocol smoke, metadata-only analysis, result identity and explicit native executor controls pass; no protocol change. |
| AC-007 | VERIFIED | Request target precedence, unknown target rejection, required parameters, scope/input drift and native `/2` exclusion pass. |
| AC-008 | VERIFIED | Stored physical dependency traces, registration before dependent start and transitive failure no-start controls pass. |
| AC-009 | VERIFIED | Captured/profile concurrency precedence, peak execution and numeric policy boundary controls pass. |
| AC-010 | VERIFIED | Real Local/Polars/Pandas source, portable step and sink preparation with typed-empty/nullable inputs pass; physical portable path retains exact descriptors. |
| AC-011 | VERIFIED | Both Arrow directions and distinct port routing/ownership controls pass in the real-backend campaign. |
| AC-012 | VERIFIED | Finite collection execution, bounds, trace and unsupported shape/policy controls pass. |
| AC-013 | VERIFIED | Output/schema validation and deadline/barrier-before-publication controls pass. |
| AC-014 | VERIFIED | Real owned checkpoints, reuse/retention/integrity, malformed state and no-partial-registration controls pass. |
| AC-015 | VERIFIED | Member failure prefix/attempt/retry safety and unqualified fused realization rejection controls pass; no fusion scope expansion. |
| AC-016 | VERIFIED | Executor failure retains terminal logical reports, downstream skips and independent branch outcomes. |
| AC-017 | VERIFIED | Step/run/boundary deadlines, native drain/abandon, cancellation cleanup and late-output fencing pass. |
| AC-018 | VERIFIED | Sole physical publication, memory/file overwrite, destination locking and explicit writer compatibility controls pass. |
| AC-019 | VERIFIED | Definite failure, committed/unknown receipts, acknowledgement loss, timeout and reconciliation obligation controls pass. |
| AC-020 | VERIFIED | Logical/physical attribution, semantic counts and differential result/report controls pass. |
| AC-021 | VERIFIED | Namespaced report writers, existing migration fixtures and recursive semantic failure/receipt privacy controls pass. |
| AC-022 | VERIFIED | Unsupported consumer/durable/dynamic rejection controls and Experimental documentation pass. |
| AC-023 | VERIFIED | Concurrent same-runtime isolation, shared/borrowed/owned lifecycle and cleanup obligation controls pass. |
| AC-024 | VERIFIED | Fresh 128/128 non-writing qualification with matching source/evidence, current docs/build and optional-free wheel imports; existing environment matrix remains unchanged. See CI limitation below. |

## Previous Blockers

| Finding | Status | Fresh verification |
|---|---|---|
| FINAL-001 | VERIFIED FIXED | Whole-DAG admission, storage/binding denial and immutable adapter replacement controls. |
| FINAL-002 | VERIFIED FIXED | Required exact diamond/fanout and directional multi-port qualification/mismatch controls. |
| FINAL-003 | VERIFIED FIXED | Real transfer, finite collection, checkpoint/reuse, malformed flag and retention controls. |
| FINAL-004 | VERIFIED FIXED | All effective-request contracts plus ordinary explicit, independent fallback and serialized engine-collision tests. |
| FINAL-005 | VERIFIED FIXED | Publication failure, acknowledgement-loss, known/unknown timeout receipt and explicit writer controls. |
| FINAL-006 | VERIFIED FIXED | Concurrent default same-runtime artifacts remain isolated. |
| FINAL-007 | VERIFIED FIXED | Native/schema/boundary/run deadlines, cleanup drain and late-result fences. |
| FINAL-008 | VERIFIED FIXED | Default source-bound non-writing verifier and fabricated/skipped/tampered evidence rejection. |
| FINAL-009 | VERIFIED FIXED | Recursive protocol/receipt privacy and semantic failure-stage controls. |
| SOL-010 | VERIFIED FIXED | Fresh documentation consistency and documentation build. |
| SOL-011 | VERIFIED FIXED | Failure returns truthful terminal logical reports and dependent/independent outcomes. |

## Quality Gates

Fresh logs: `/tmp/sol053-fallback-fixed-*.log`.

| Gate | Executed | Result |
|---|---|---|
| Protected and adjacent targeted suites | Yes | PASS — 59 tests, 3 warnings, 32.70s |
| Configured core marker suite | Yes | PASS — 1865 passed, 5 skipped, 407 deselected, 50 warnings, 142.12s |
| Default non-writing adaptive 0.53 verifier | Yes | PASS — 128 executed/pass, no skips, source_changed=false; matching evidence |
| Default historical adaptive 0.52 verifier | Yes | PASS — 10 artifacts, 18 criteria |
| Whole-repository Ruff lint and format | Yes | PASS — 951 formatted files |
| Configured Pyright | Yes | PASS — zero errors/warnings |
| Explicit Pyright on resolver and fallback tests | Yes | PASS — zero errors/warnings |
| Documentation consistency | Yes | PASS — internal links/anchors; external URLs inventoried, not fetched |
| Documentation build | Yes | PASS — /tmp output, 21.83s |
| Release metadata checks | Yes | PASS — existing 0.52.1 development-base metadata |
| Surface inventory and diagnostic stability | Yes | PASS |
| Stable protocol freeze and plugin manifests | Yes | PASS |
| Security matrix and agent guidance | Yes | PASS |
| Stable foundation | Yes | PASS — 21 tests, coverage 21/21 |
| Core sdist/wheel build | Yes | PASS — /tmp artifacts |
| Isolated core wheel import | Yes | PASS — physical protocol imports without Polars/Pandas |
| Final diff whitespace/scope inspection | Yes | PASS — staged remediation preserved |

Environment: macOS arm64, Python 3.11.15, core 0.52.1, Polars 1.42.1,
Pandas 2.3.3, PyArrow 25.0.0. No gate failed and no expected-failure, discovery
exclusion or gate suppression was added.

CI limitation: No fresh remote CI was executed for this uncommitted staged
candidate. The previously reviewed 37-job matrix belongs to HEAD `5100e9c4`
and is not reported as a current-candidate CI pass. The five-family portable
physical path and existing matrix configuration are unchanged; the repair is
the shared Python native resolver's request-origin distinction, exercised
freshly here. This evidence is sufficient for the bounded production re-review;
it does not grant new environment qualification or independent final release
approval. Publishing the candidate must retain the existing CI gates.

## New Blockers

None.

## Follow-Ups

| Finding | Severity | GitHub |
|---|---|---|
| SOL-012 — Pre-existing Medallantic migration fingerprint goldens | Low | EXISTING ISSUE #145, confirmed OPEN |
| Deadline verification sensitivity to compiler startup | Low | EXISTING ISSUE #146, confirmed OPEN |

No new follow-up was established. Existing findings remain outside this
remediation boundary and do not prevent this change from satisfying its
contract. No duplicate GitHub issue was created.

## Observations

None requiring action.

## Convergence

- Previously open blockers resolved this iteration: 1, FINAL-004.
- Other previously resolved blocker findings independently revalidated: 10.
- Blockers remaining: 0.
- New blockers attributable to remediation: 0.
- New follow-ups: 0.
- The loop has converged for the approved phase 0.53 production contract.

**PASS**
