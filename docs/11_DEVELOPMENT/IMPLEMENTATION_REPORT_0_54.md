---
status: experimental
since: "0.54.0"
current_minor: "0.54"
audience: developer
---

# 0.54 initial implementation report

The bounded implementation and final stable-source observation verification are
complete. This is not independent approval, production readiness or adaptive
graduation. All fourteen candidate rows remain Experimental; graduation is
pending.

## Release fact

ETLantic **0.54.0** was published on **2026-09-19**. The immutable
[`v0.54.0` tag](https://github.com/eddiethedean/etlantic/releases/tag/v0.54.0)
points to commit `7b477249b5a7e906e7f862b8d5a89e616590e864`; the [release
workflow](https://github.com/eddiethedean/etlantic/actions/runs/35457133070)
completed all 38 checks successfully and published all 24 PyPI distributions.
This publication fact does not promote the Experimental adaptive rows to
Available.

## Requirements

These statuses apply to the approved **local initial-implementation boundary**.
Remote CI execution is recorded in the release fact above; an independent
adaptive graduation decision remains follow-up work.
The [frozen catalogue](evidence/adaptive_0_54/case_catalogue.json) maps all 24 local
and all 24 program criteria to full pytest identities, all fourteen row signatures,
and seventeen sanitized category reports.

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

Paths in the table are under `src/etlantic`, the optional Polars package, or
`tests/adaptive_conformance` / `tests/runtime/physical` as appropriate.
Full exact test paths and parameters are in the catalogue.

## Changes and architectural decisions

- Added a read-only optional Parquet source with finite byte/row/column limits,
  primitive physical-schema checks including dropped columns, safe relative-file
  handles, sanitized immutable byte snapshots and native-worker ownership.
- Added immutable original portable-member descriptors, alpha-renamed composition,
  protected-boundary recognition and one fused physical compute unit. Region
  fusion evidence/identity now matches the actual physical descriptor.
- Kept the existing solver and frozen objective. The candidate binds all five
  placements explicitly, so positive fusion/pushdown credit is assignment-independent;
  partially bound placement receives neither hypothetical credit nor fusion.
  This conservative exact-signature boundary is documented in the architecture plan.
- Whole-DAG admission pins the actual qualified adapter/compiler, stored IR,
  contracts, binding and workspace policy before effects. Fused execution does
  not substitute ordinary sequential node execution or expose eager intermediates.
- Added public provider conformance without trust/maturity mutation, fresh
  observation/verification/aggregation tooling and locally tested graduation safeguards.
- Prepared core plus 23 workspace packages at 0.54.0, dependency ranges, lockfile,
  fifteen manifests and current-facing documentation. Publication is recorded
  separately in `docs/release-facts.json`.
  No database migration, new core engine dependency, general fusion, connector-session
  expansion, durable queue or control-plane expansion was introduced.

## Tests added and modified

The frozen phase catalogue contains **642 exact cases**, including **339 new
0.54 cases** and retained adaptive compatibility/runtime regressions.
New coverage includes real source/fused-query/Arrow/Pandas effects, typed explicit
parity, nullable empty inputs, duplicate/order semantics, bounds and unsafe paths,
atomic drift, cancellation, deadlines, concurrency, cleanup ownership, safe
provider reports, provenance tampering, aggregation and pending/go/no-go guards.

The existing 0.53 schema-deadline probe now synchronizes boundary entry instead
of depending on startup within 100 ms. Current plugin compatibility pins were
aligned to 0.54. Migration fingerprint goldens were requalified: comparison with
the clean baseline proved their only definition difference was package-version
provenance 0.53.0 → 0.54.0. Assertions were retained; historical wire/evidence
fixtures were not rewritten.

## Quality gates actually executed

Counts describe separate overlapping runs, not additive distinct coverage.

| Check | Actual result |
|---|---|
| Latest broad repository `pytest -q tests --tb=short` | 2,658 passed, 29 skipped, zero failures in 534.14s |
| Prior phase catalogue | Attempt 8: 629 passed, zero skipped, 81 visible warnings in 346.17s; observation and all 17 category hashes/semantics verified against its recorded source |
| Current phase catalogue | Attempt 13: 642 passed, zero skipped, 84 visible warnings in 328.70s; identical before/after/current source and all 17 category hashes/semantics verified |
| Fresh prior-adaptive 0.53 campaign with `--write` to an isolated temporary directory | 128 scenarios passed; actual Darwin/arm64/Python 3.11.15 and 0.54 package version retained |
| Focused region/objective/wire verification | Two passed before final coherence guard; covered again by final catalogue |
| Evidence/graduation mechanisms | Passing focused runs, including 36 evidence cases; synthetic matrix fixtures are not actual CI proof |
| `ruff check .`, `ruff format --check .` | Passed; 981 Python files formatted |
| `pyright --pythonpath .venv/bin/python` | Zero errors/warnings |
| `uv lock --check`, plugin manifests, surface inventory | Passed; 230 locked packages, fifteen manifests, 19 curated exports / 17 namespaces |
| Pipeline and sibling codec burn-in | Passed: 32 and 44 fixtures |
| Isolated codec burn-in | Passed: 30 cases, zero skipped; regenerated content unchanged |
| Stable foundation | Passed: 21/21 acceptance tests |
| Protocol freeze, diagnostic stability, security matrix, agent guidance | Passed: six frozen families, 36 diagnostic families, 21 controls and guidance alignment |
| Portable 0.50 evidence and transform-compiler drift | Passed |
| Connector/durable/CP4/registry/objective fake conformance and isolation/chaos | Passed locally |
| CP-GA compatibility/isolation/resilience/recovery/capacity/security/operations/GitOps fake campaigns | Passed after current-version compatibility requalification |
| Documentation consistency, CLI/API coverage, internal links/anchors, runnable companions | Passed; 23 top-level / 77 collected CLI commands, fifteen runnable companions |
| Strict MkDocs builds | Passed, including final report rendering |
| All-package wheels and sdists | All 24 distributions built; core and Polars rebuilt after review corrections |
| Isolated core-only wheel | Engine-free public imports passed without Polars/Pandas/Arrow |
| Latest isolated optional Polars/Pandas wheels and exact backends | Public reference and 63 admission/lifecycle/source/fusion checks passed against rebuilt core and Polars; 17 visible warnings |
| `etlantic doctor --format json` and `git diff --check` | Passed |
| Historical `check_adaptive_0_52.py` / evidence-regeneration test | Passed after canonical regeneration of the current-tree 0.52 evidence artifacts |
| Index verification with absent actual matrix | Correct nonzero integrity/completeness rejection; no cross-platform claim |

The initial bare Pyright invocation selected the wrong interpreter and reported
missing optional imports; the explicit workspace interpreter passed without
suppressions. Initial release/docs/compatibility version drift was corrected,
then the affected gates rerun. Release metadata checks passed and confirmed all
24 versioned PyPI artifacts were still absent at this prepublication checkpoint;
the subsequent tagged release published them.

## Remaining issues and limitations

There are no known unresolved implementation issues within the approved bounded
scope. No requirement is marked PARTIALLY IMPLEMENTED or BLOCKED under the local
completion boundary.

The [current local observation](evidence/adaptive_0_54/local/attempt-13/observation.json)
records 642 passing cases on Darwin/arm64, Python 3.11.15, with the exact pinned
backends and all seventeen category artifact hashes. Source digests before and
after execution match. This is an uncommitted-workspace local observation, not
a clean-commit CI observation. Earlier failed, changed-source and interrupted
attempts remain retained honestly. Report/status documents are excluded from the
source digest to avoid circular evidence finalization.

The whole repository is now green for the local suite: 2,658 tests passed and
29 optional/environment-dependent tests were skipped. The historical
`test_final_052_006_evidence_regenerates_cleanly` blocker was resolved by
regenerating the committed 0.52 evidence artifacts with the canonical checker;
the refreshed artifacts preserve the same scenarios and record the current
source and plan fingerprints. Optional skips and legacy metadata warnings remain
visible.
Prefect emitted an existing shutdown logging error after pytest completion.

This initial local report did not itself execute the release-owner action or
make an independent adaptive graduation decision. The subsequent tagged
v0.54.0 release workflow completed the Linux/macOS/Windows × Python
3.11/3.12/3.13 checks and published the release. Local synthetic matrix/go
fixtures validate safeguards only; they are not remote evidence or approval.
The runtime candidate remains exact-signature and Experimental, with the new
fusion row restricted to development/test. No general source pushdown or fusion
claim is made. No additional architectural decision is required to run this candidate.

## Handoff

### Follow-up corrections: issues #143 and #144

Control-plane collections now check concrete resources with their collection
actions before serialization and existing limits. Memory and SQLModel-backed
graphs cover collection denial without repository access, object denial,
list/read independence, scope, limit growth and authorization-service failure
without partial results. Other item-authorized collections retain their parent
gates and gain concrete checks; audit export retains its separate complete
hash-chain evidence contract.

All control-plane routes now use public `RedactedValidationRoute` to return a
fixed safe HTTP 422 envelope without reading or logging invalid inputs or
validation context. It applies in standalone and embedded apps without global
handler replacement. Exported `request_validation_error_handler` supports
explicit application-wide registration; its collision and unrelated-host-route
behavior are documented in the adapter README and control-plane API guide.

The adapter/provider regression run passed **191 tests**, with three optional
skips. The **50 new issue regressions** also passed against built core/FastAPI/
SQLModel wheels in a fresh isolated environment, with repository source paths
disabled. Adapter wheel and sdist builds, Ruff, Pyright, documentation consistency
and strict rendering passed. These results are separate overlapping runs, not
additive counts. The existing broad full-suite result above predates these fixes.
The 482-case phase campaign also passed again with stable-source observation
verification after these corrections. Neither GitHub issue was closed; published
artifact qualification requested by #143 remains recorded in the release fact
above as a separate release action.

At the time of this report, changes were uncommitted and no tag, push, release
or Available promotion had been performed. The later release fact records the
immutable tag and publication; it does not promote adaptive rows.

### Review finding remediation

All five review findings are fixed locally:

| Finding | Correction |
|---|---|
| Custom contract hooks could gain fusion authority | Planner and runtime admission reject overridden validation/construction hooks and noncanonical compiled core schemas |
| Failed snapshot cleanup lost its owner | Superseded by immutable byte snapshots: no replaceable disk path or disk cleanup owner remains |
| CI proof output dirtied the checkout | Proof production, upload, download and aggregation use `runner.temp`; source cleanliness checks remain enforced |
| Names were mistaken for native plan operators | Operator checks are line-anchored and preserve quoted-name whitespace; real keyword paths/columns and an actual standalone FILTER negative case are covered |
| FastAPI CI silently skipped SQLModel coverage | Job installs the SQLModel dependency group and requires provider imports rather than allowing optional skips |

The expanded stable phase campaign passed **494 cases**. The broader adapter,
provider and storage run passed **234 tests**, with three optional skips. All
**13 targeted review regressions** passed against isolated rebuilt wheels.
Counts overlap. Ruff, explicit-interpreter Pyright, wheel/sdist builds and strict
documentation rendering passed. The initial report did not claim remote CI; the
subsequent release workflow passed all 38 checks.

Attempt 6 remains recorded: it was intentionally interrupted to complete the
native-plan parser correction, causing cancellation of a running test and a
nonpassing, changed-source observation. Attempt 7 records the prior stable source, before the second review corrections.
Buffer ownership and native drain are documented in the Polars README and migration
guide. The current source creates no disk snapshot cleanup obligations; uncertain
publication and other native/checkpoint obligations still require their own recovery.

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

Focused checks: 137 evidence/graduation tests, 23 admission tests, 29 lifecycle/public
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
The earlier broad-run retained-evidence mismatch is resolved by the canonical
0.52 artifact regeneration. The transient admission failure passed on
frozen-source rerun and in both the final campaign and installed-wheel checks.
No failures are suppressed.

## Third review remediation

All four remaining findings are fixed locally:

- Public conformance supplies request parameter overrides to validation; required
  request-only parameters now work in planning and stored execution, while missing
  parameters still reject without execution.
- Native cancellation delivery time is captured before shielded drain. Fused
  logical states and terminal reports preserve caller cancellation even if a step
  or run deadline expires during cleanup; actual deadlines remain timed out.
- Native proof masks exact column tokens only for operator detection and checks
  predicate identity against original text. Multiline operator-like identifiers
  work, wrong-column predicates and standalone FILTER operators still reject, and
  stored fused execution matches ordinary explicit typed results.
- Evidence JSON is parsed and hashed from one bounded read. Qualification uses
  the verified index digest and already-validated observation records, without
  reopening mutable files. Index, observation and category replacement tests
  retain the original verified snapshot rather than qualifying replacement bytes.

The catalogue retains all 629 prior cases and adds thirteen regressions. The
22-case source/parser check, 88-case lifecycle/native/evidence check, 50 issue
#143/#144 tests, and 22 tests against rebuilt installed wheels passed. Counts
overlap. Ruff, formatting, explicit-interpreter Pyright and documentation checks
passed. The wheel run used actual Polars 1.42.1, Pandas 2.3.3 and PyArrow 25.0.0;
three pre-existing metadata warnings remain visible.

[Attempt 9](evidence/adaptive_0_54/local/attempt-9/observation.json) ran all 642
cases successfully, but is correctly nonpassing evidence because the final
wrong-column guard landed during the run. Its before/after digests differ; it is
retained, not relabeled as stable-source proof.

The final [attempt 10 observation](evidence/adaptive_0_54/local/attempt-10/observation.json)
passed all **642 cases** in **344.90s**, zero skips, with 84 visible warnings.
Its before/after/current source digest is
`sha256:e96d2da29531535af267536d7de19648f912b4f5340154d2b41bd5e397caf5ee`;
all seventeen category hashes and semantic records were verified independently.
Candidate graduation remains pending; this evidence snapshot itself did not
commit or publish.
