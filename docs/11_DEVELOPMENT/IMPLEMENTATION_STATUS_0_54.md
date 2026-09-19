---
status: experimental
since: "0.54.0"
current_minor: "0.54"
audience: developer
---

# 0.54 initial implementation status

The bounded local implementation and final stable-source evidence verification
are complete. This ledger is not independent approval or adaptive graduation.
All fourteen candidate rows are Experimental and graduation is pending. The
release workflow and external checks are complete; independent adaptive approval
remains a separate follow-up.

## Release fact

ETLantic **0.54.0** was published on **2026-09-19**. The immutable
[`v0.54.0` tag](https://github.com/eddiethedean/etlantic/releases/tag/v0.54.0)
points to commit `7b477249b5a7e906e7f862b8d5a89e616590e864`; the [release
workflow](https://github.com/eddiethedean/etlantic/actions/runs/35457133070)
completed all 38 checks successfully and published all 24 PyPI distributions.
Publication records the release only; it does not promote the Experimental
adaptive rows to Available.

## Requirements checklist

| Local criterion | Status | Relevant files / symbols | Covering tests |
|---|---|---|---|
| AC-001 public conformance | IMPLEMENTED | `testing/adaptive.py`: immutable case/report; sync/async provider suites | `test_public_suite.py`: validation, loop guard, factories, cancellation |
| AC-002 behavioral claims | IMPLEMENTED | Required in-process oracles; `etlantic_polars/fusion.py`: native scan proof | Public suite, actual fused-query dispatch; independent directional qualification |
| AC-003 no implicit authority | IMPLEMENTED | Safe conformance report; packaged candidate separate from historical qualification | Unqualified-provider zero-read rejection, hostile serializers, isolated public example |
| AC-004 bounded source | IMPLEMENTED | `etlantic_polars/parquet_storage.py`: frozen adapter/factory, safe owned snapshot | 60 storage cases; bounded buffers, footer safety and native ownership tests |
| AC-005 exact eligibility | IMPLEMENTED | `planning/fusion.py`: primitive contracts, exact topology, policy exclusions | Protected boundaries, partial placement, retry, middleware and source drift |
| AC-006 IR / wire identity | IMPLEMENTED | `transform/fusion.py`, `plan/physical.py`, `adaptive_model.py`; closed JSON schemas | Alpha-renaming, round trip, internal-route/IR tampering, immutable descriptors |
| AC-007 actual fusion | IMPLEMENTED | `runtime/fused_execution.py`; one native query; qualified compiler dispatch | Single collect, no intermediate node bodies/artifacts, Arrow/Pandas/validation/publication |
| AC-008 fourteen rows | IMPLEMENTED | `adaptive_candidate.json`; exact row catalogue, reverse direction independent | Five chain families, six branch families, two dual-port directions, fused reference |
| AC-009 typed differentials | IMPLEMENTED | Ordinary explicit path preserved; nullable annotation typing corrected | Explicit/adaptive typed lifecycle parity; empty/null/duplicate/no-match cases |
| AC-010 failures / deadlines | IMPLEMENTED | Existing native drain/fencing plus safe fused member attribution | Boundary-synchronized deadline, cancellation, compile failure, no late publication |
| AC-011 lifetime / concurrency | IMPLEMENTED | Immutable buffer retained through native drain; no disk snapshot artifacts | Concurrent runs, input replacement, cancellation/drain, native owner release |
| AC-012 physical effects | IMPLEMENTED | Existing seven-kind scheduler, checkpoint/reuse and publication authority | Bounds, checkpoints, validation, definite failure, acknowledgement loss, receipts |
| AC-013 atomic admission | IMPLEMENTED | `adaptive_admission.py`: source/compiler/IR/contracts/policy pins | Zero-effect drift/denial cases, live replacement and captured-binding tests |
| AC-014 safe artifacts | IMPLEMENTED | Generic native diagnostics; digest-only query proof and closed safe evidence | Serializer/exception/row canaries, receipt rejection, evidence tamper cases |
| AC-015 compatibility | IMPLEMENTED | Separate /1 and /2; historical readers and qualification retained | Wire corpus, explicit/fallback regressions, codec burn-in and stable foundation |
| AC-016 effective precedence | IMPLEMENTED | Captured effective Profile/request, bindings, parameters and selections | Effective-request, explicit/fallback override and serialized-definition suites |
| AC-017 report migration | IMPLEMENTED | Existing namespaced report migration retained; new proof fields namespaced | `test_metadata_namespace_0_51.py`: legacy, collisions, repeat/idempotent reads |
| AC-018 solver / resources | IMPLEMENTED | Exact additive objective credits; owned descriptor/region allocations | Independent oracle, exact/first-excess budgets, permutation seeds 0–15, hash seeds 0/1/42 |
| AC-019 fresh observations | IMPLEMENTED | `check_adaptive_0_54.py`: actual provenance, full IDs, before/after source digest | Status/provenance tests; failed and interrupted runs retained honestly |
| AC-020 read-only index | IMPLEMENTED | `adaptive_0_54_evidence.py`: closed catalogue/index/observation validation | Missing/skipped/failed/duplicated/cross-source/tampered cases, paths and hashes |
| AC-021 observed aggregation | IMPLEMENTED | Nine-cell same-candidate verifier; CI uploads and dependent aggregation job | Synthetic temporary nine-cell matrix acceptance and completeness/provenance rejection |
| AC-022 promotion safeguards | IMPLEMENTED | `adaptive_graduation.py`: independent go and weakest-link validation | Pending/no-go/overclaim, mandatory primary/reverse, owners, date, findings and evidence |
| AC-023 docs / operations | IMPLEMENTED | Public executable reference; provider/API/usage/migration guides and navigation | Isolated wheel reference; finite quarantine/replan; prior drain/receipt/checkpoint tests |
| AC-024 pending decision / self-check | IMPLEMENTED | Closed packaged pending decision; catalogue, ledger and this report | Candidate/graduation validation; local quality gates and scoped baseline comparison |

The [implementation report](IMPLEMENTATION_REPORT_0_54.md) records the changes,
actual checks, exact-signature limits and remaining baseline findings.
The [frozen catalogue](evidence/adaptive_0_54/case_catalogue.json) supplies full
pytest identities for all 24 local/program criteria and fourteen rows.

## Verification and scope

The latest broad suite produced 2,658 passes, 29 skips and zero failures in
534.14 seconds. The current 0.54 local observation passed all 642 frozen cases
with zero skips and identical before/after source digests. The prior stable
629-case catalogue and its
[local observation](evidence/adaptive_0_54/local/attempt-8/observation.json)
remain retained, and earlier unsuccessful observations remain retained rather
than replaced.

The retained 0.52 evidence was regenerated with the canonical checker after the
current-tree source and plan fingerprints changed. The regeneration test and
non-writing verifier now pass against the refreshed artifacts.

Core and 23 optional packages, manifests, dependency ranges and lock metadata
are at 0.54.0. All distributions built; isolated engine-free core and real optional
wheel checks run independently. Historical qualification/wire evidence is retained;
ordinary /1 does not gain adaptive metadata.

No database migration or new core engine dependency was introduced by the
implementation, and no Available-row promotion was performed. Release
publication, tagging and push are recorded above and remain separate from this
implementation ledger.

## Second review remediation

All sixteen findings are fixed locally. Admission now ties fused source/member/edge
contracts, effective parameters and required physical barriers to the logical plan.
New plans fingerprint bounded JSON-safe effective parameter values; the host restores
those values after deserialization without changing historical wire serializers.
Legacy parameterized plans lacking capture require replanning before execution.

The source scans sanitized immutable bytes, preventing pathname replacement and
extension deserialization before primitive checks. Actual escaped-column native
proof works, and explicit source compatibility remains PyArrow >=14. Known native
panics produce safe terminal reports; caller cancellation propagates after drain,
and all active fused members retain timed-out states without late publication.

Evidence source ordering uses POSIX-relative keys. Relative indexes resolve before
containment checks; category contents are semantically validated, not only hashed.
Candidate rows require exact pins/operations/policies. Every go row, including an
Experimental row, requires source/index/row-bound verified qualification. Pending
records remain pending; synthetic verifier fixtures are not actual remote proof.

## Third review remediation

All four remaining findings are fixed: request overrides reach public conformance
validation; caller cancellation is classified before native drain and survives
later run deadlines; multiline names are masked only for native operator parsing,
with exact predicate identity retained; and qualification hashes and parses the
same bounded evidence snapshots without reopening observations.

Thirteen regressions expand the frozen catalogue to 642 cases, retaining all
629 earlier cases. Wrong-column and standalone FILTER negative checks also pass.
The refined source/parser check passed 22 cases; rebuilt installed wheels passed
22 selected regressions. The issue #143/#144 suite passed 50 cases, and the
lifecycle/native/evidence run passed 88. Counts overlap; Ruff, formatting,
explicit-interpreter Pyright and docs checks passed.

Attempt 9 passed all 642 tests but retains a nonpassing observation because the
final predicate-identity guard changed the source during execution.

The current [attempt 11 observation](evidence/adaptive_0_54/local/attempt-11/observation.json)
passed all 642 cases in 356.89s, zero skips, with 84 visible warnings. Its
identical before/after/current source digest is
`sha256:7f3ab7fdd3bd6e33c92e3483f976f285283b9b77ff1f0b6d36f5a3d4a0b771fc`.
All seventeen category hashes and semantics were verified. This observation is
a historical local snapshot; it did not commit, push, publish, or graduate a
row.

## Prior verification and follow-ups

Prior focused checks: 137 evidence/graduation tests, 23 admission tests, 29 lifecycle/public
suite tests and 112 source/fusion/review tests passed. Counts overlap. All 63 admission/lifecycle/source/fusion checks passed against installed
rebuilt wheels (107.67s). Actual isolated
Arrow 14 regressions passed 17 cases, and Arrow 20 storage passed 60. Core and Polars
wheel/sdist builds, engine-free core imports, the installed-wheel public reference,
Ruff, Pyright, docs checks/strict rendering and 21 stable-foundation tests passed.

The retained [attempt 8 observation](evidence/adaptive_0_54/local/attempt-8/observation.json)
passed all **629 cases** in **346.17s**, zero skips, with 81 visible warnings.
Its before/after source digest is
`sha256:23aafa43c0e4af3d76eb9f7ea507e7ebd2360c20408b9f825e914b4f2dd9398f`;
all seventeen category hashes and semantic records were verified independently.
Attempts 1–7 remain historical observations of their own earlier catalogues/sources.
The earlier broad-run retained-evidence mismatch is resolved; no failures are
suppressed. The transient admission failure from that earlier run passed on the
frozen-source rerun and in the final campaign and installed-wheel checks.

Next: **Sol — Production Code Review**.

Follow-up issues #143/#144 are implemented locally: concrete collection list
denials and route-scoped safe validation errors. Adapter/provider tests passed
191 cases (three skips); all 50 issue regressions passed against isolated built
wheels. GitHub issue closure was not performed. Release publication is recorded
above; see the implementation report for adaptive qualification boundaries.

All five subsequent review findings are fixed: custom contract hooks fail closed,
immutable buffers eliminate replaceable disk snapshots and disk cleanup obligations, CI proofs stay
outside the checkout, native operator detection distinguishes names from plan
operators, and FastAPI CI requires SQLModel coverage. Twelve new catalogue cases
cover these corrections. The broader adapter/provider/storage run passed 234
tests (three skips); 13 targeted regressions passed against isolated rebuilt
wheels. The prior 629-case campaign includes these and all sixteen second-review fixes.
Release workflow checks and publication are recorded above; adaptive graduation
remains unclaimed.
