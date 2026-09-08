# Exit Gate 0.50 — Seven-Engine Portable Execution and Pushdown Conformance

> **Status: Technical qualification complete; Sol review pending.** The checked-in
> evidence records a passing real-backend campaign, but does not itself grant
> release approval. The final decision is recorded by
> [task #109](https://github.com/eddiethedean/etlantic/issues/109).

See the [0.50 implementation plan](IMPLEMENTATION_PLAN_0_50.md),
[epic #102](https://github.com/eddiethedean/etlantic/issues/102), and
[0.50 milestone](https://github.com/eddiethedean/etlantic/milestone/2).

## Target Claim

| Surface | Target at gate | Entry state |
|---|---|---|
| Baseline manifest | Public `etlantic.portable-baseline/1` authority over [DTCS](../04_TRANSFORMATIONS/DTCS.md) plan `/2`, both relational `/1` profiles, 12 actions, 30 functions, and governed operators | Passing immutable evidence generated |
| Requirement/support protocol | Public applicability plus two-axis obligation/support model with requirement-level evidence | Passing requirement-level evidence generated |
| Compatibility | Additive `etlantic.transform-compiler/1` evidence; `etlantic.plan/1` stays readable while stale/evidence-free plans require replanning before execution | Preflight and drift regressions pass |
| Pushdown protocol | Complete applicability and outcome matrix; only declared SQL/DuckDB/native-plan boundaries are required | Passing boundary matrix generated |
| Local | Baseline Available without optional dataframe/database dependencies | Passing corpus and canonical run |
| Polars | Baseline Available for declared eager/lazy modes | Passing corpus and canonical run |
| Pandas | Baseline Available for declared eager mode | Passing corpus and canonical run |
| SQL | Baseline Available through normal runtime for SQLite and PostgreSQL | SQLite and real-PostgreSQL corpus passes |
| PySpark | Baseline Available on real JVM Spark with canonical engine identity | Real-JVM corpus and canonical run pass |
| DataFusion | Baseline Available through native expressions | Passing corpus and canonical run |
| DuckDB | Baseline Available through the qualified native package and pushdown contract | Full baseline and pushdown corpus pass |
| Advanced profiles | Engine-specific, separately claimed | Uneven by design |
| Native implementation bodies | Explicit escape hatch only | Available; must not become implicit fallback |
| Adaptive, streaming, remote, and federated execution | No 0.50 claim | Out of scope |

No baseline engine row may be omitted from the phase decision. A failing row or
required applicable pushdown finding makes the shared seven-engine claim a
no-go. An explicit `not_applicable` finding passes only where the frozen
manifest says no external boundary exists; it cannot disguise unsupported
pushdown. DuckDB's 0.49 package gate is a prerequisite, while this gate owns its
baseline and pushdown qualification. Sol independently reviews the campaign
before any release decision.

## Quantified Exit Scorecard

| # | Measure | Required | Current | Owner |
|---|---|---:|---|---|
| 1 | Normative manifest freezes DTCS plan/profile identity, 12 actions, 23 scalar and 7 aggregate functions, governed operators, aliases, types, modes, joins, unions, collisions, and semantic edge cases | Pass | **Evidence complete — review pending** | #103, #106 |
| 2 | `/2` profile aliases prove exact normalization to the `/1` baseline or are removed with migration evidence | Pass | **Evidence complete — review pending** | #106, #109 |
| 3 | `etlantic.transform-compiler/1` remains additive, legacy omissions normalize to `unknown`, and 0.49 `etlantic.plan/1` fixtures remain readable but fail preflight until replanned | Pass | **Evidence complete — review pending** | #106 |
| 4 | Every advertised baseline claim maps to a mandatory public fixture and every required baseline item is claimed | 100% | **Evidence complete — review pending** | #107 |
| 5 | Applicability, requirement obligation (`required`, `preferred`, `informational`), and target support (`supported_exact`, `supported_with_lowering`, `unsupported`, `unavailable`, `unknown`) are independently represented and fingerprinted | Pass | **Evidence complete — review pending** | #103, #106 |
| 6 | Required unknown, omitted, unsupported, unavailable, ambiguous, and unresolved-conditional requirements fail during validation/planning with stable diagnostics | Pass | **Evidence complete — review pending** | #103, #106, #107 |
| 7 | Lowering-backed support records a stable lowering identity, resolved conditions, proof evidence, and physical effects; invalid or data-dependent conditions fail closed | Pass | **Evidence complete — review pending** | #106, #107 |
| 8 | Every declared boundary emits one deterministic applicability/outcome finding; required SQL, DuckDB, PySpark, and DataFusion native-plan boundaries have positive executable proof | Pass | **Evidence complete — review pending** | #96–#108, #118 |
| 9 | Local validates, plans, and runs the canonical portable-only pipeline with no optional engine dependency | Pass | **Evidence complete — review pending** | #96 |
| 10 | Polars passes the complete baseline in both claimed eager/lazy modes | Pass | **Evidence complete — review pending** | #97 |
| 11 | Pandas passes the complete baseline with index-neutral, explicit dtype/null behavior | Pass | **Evidence complete — review pending** | #98 |
| 12 | SQLite and PostgreSQL run portable SQL through normal pipeline dispatch and preserve handles until declared boundaries | Pass | **Evidence complete — review pending** | #99 |
| 13 | SQL parameters remain bound and portable syntax cannot introduce raw/trusted fragments | Pass | **Evidence complete — review pending** | #99 |
| 14 | Real JVM PySpark passes the complete baseline without Python/Pandas UDF fallback | Pass | **Evidence complete — review pending** | #100 |
| 15 | `spark` and `pyspark` resolve to one authorized identity, or the alias is removed with compatibility evidence | Pass | **Evidence complete — review pending** | #100 |
| 16 | DataFusion analysis, native lowering, execution, and Arrow boundaries pass the complete baseline | Pass | **Evidence complete — review pending** | #101 |
| 17 | DuckDB native package passes baseline execution and emits complete pushdown findings with explain/boundary evidence | Pass | **Evidence complete — review pending** | #118 |
| 18 | Every engine emits truthful requirement-level evidence; shared negative fixtures cover partial, unavailable, unknown, and rejected slices; only complete manifest coverage earns baseline qualification | Pass | **Evidence complete — review pending** | #96–#109, #118 |
| 19 | One unchanged authored pipeline validates, plans, and runs on all seven baseline engines | 7/7 | **Evidence complete — review pending** | #108, #118 |
| 20 | Normalized differential and pushdown corpus agrees for nulls, empty input, Unicode, numerics, ordering, joins, unions, aggregation, deduplication, and declared boundaries | 7/7 | **Evidence complete — review pending** | #108, #118 |
| 21 | The 0.50 evidence artifact drives a 0.51-style per-node eligibility fixture without engine-name or aggregate-qualification inference | Pass | **Evidence complete — review pending** | #106–#109 |
| 22 | Required support failures eliminate candidates before preference scoring; preferred unknowns receive no positive benefit | Pass | **Evidence complete — review pending** | #107, #108 |
| 23 | Every optional engine passes clean isolated install/import and core dependency-boundary checks | Pass | **Evidence complete — review pending** | #96–#101, #108, #118 |
| 24 | Plans, reports, diagnostics, examples, and evidence contain no source rows, executable objects, raw SQL escape hatches, or secrets | Pass | **Evidence complete — review pending** | #106–#109 |
| 25 | Capability matrix is generated from or verified against machine-readable requirement-level release evidence | Pass | **Evidence complete — review pending** | #108, #109 |
| 26 | Reference, migration, rollback, 0.51 handoff, example, and explicit non-claim documentation passes strict checks | Pass | **Evidence complete — review pending** | #109 |
| 27 | No unresolved critical/high correctness, compatibility, security, or data-loss finding | 0 | **Evidence complete — review pending** | #109 |
| 28 | Final evidence locations, commands, outcomes, approvers, limitations, and decision are recorded | Pass | **Evidence complete — review pending** | #109 |

## Required Evidence Manifest

All artifacts are stored under
`docs/11_DEVELOPMENT/evidence/portable_0_50/`. Filenames are frozen so CI and
the final decision can validate completeness. Each JSON artifact must include a
schema/version, repository commit, generating command, environment summary,
result, and reproducible test links. Artifacts must be bounded and contain no
source rows, resolved secrets, executable objects, or absolute host paths.

| Artifact | Required content | Status |
|---|---|---|
| `portable_evidence_index_0_50.json` | Relative paths, logical artifact IDs, schema versions, SHA-256 digests, generating commands, commit, environments, and outcomes for every row below | Generated |
| `portable_baseline_contract_0_50.json` | Normative profiles/actions/functions/operators/modes, semantic rules, obligation levels, and applicability | Generated |
| `portable_pushdown_contract_0_50.json` | Boundary identities, applicability rules, obligations, exact/lowered/not-pushed outcomes, physical effects, and evidence requirements | Generated |
| `portable_requirement_support_0_50.json` | Requirement-level support states, compiler/target identities, reason codes, evidence fingerprints, conditional/lowering proofs, and physical effects | Generated |
| `portable_claim_coverage_0_50.json` | Compiler claim-to-mandatory-fixture coverage with no orphan, missing, overstated, or falsely aggregate rows | Generated |
| `portable_local_conformance_0_50.json` | Dependency-free Local planning, execution, diagnostics, and dependency boundary | Generated |
| `portable_polars_conformance_0_50.json` | Complete baseline in every claimed eager/lazy mode | Generated |
| `portable_pandas_conformance_0_50.json` | Complete baseline with dtype, null, index, and eager semantics | Generated |
| `portable_sql_conformance_0_50.json` | SQLite/PostgreSQL runtime, handles, parameters, boundaries, dialect rejection | Generated |
| `portable_pyspark_conformance_0_50.json` | Real-JVM baseline, alias identity, Catalyst plan, no-UDF evidence | Generated |
| `portable_datafusion_conformance_0_50.json` | Native analysis/lowering/runtime and Arrow-boundary evidence | Generated |
| `portable_duckdb_pushdown_0_50.json` | DuckDB baseline, pushdown matrix, accepted/rejected boundaries, explain evidence, and physical effects | Generated |
| `portable_cross_engine_0_50.json` | Canonical pipeline plus normalized differential and pushdown corpus across the seven baseline engines | Generated |
| `portable_canonical_pipeline_0_50.json` | Engine-neutral canonical pipeline shape with no source rows or engine-specific bodies | Generated from the passing campaign |
| `portable_adaptive_handoff_0_50.json` | 0.51-style partial-engine per-node eligibility, hard-failure, preferred-unknown, lowering-effect, and drift fixtures | Generated |
| `portable_dependency_security_0_50.json` | Isolated installs, core dependency boundary, fail-closed and redaction scans | Generated |
| `FINDINGS_0_50.md` | Triaged findings with zero unresolved critical/high at decision time | Generated |
| `MIGRATION_0_49_TO_0_50.md` | Baseline contract, plugin repin/reconformance, stored-plan replanning, engine selection/aliases, native bodies, and rollback | Generated |
| `WHATS_NEW_0_50.md` | Exact Available matrix and explicit advanced/non-engine claims | Generated |

CI runs `scripts/check_portable_0_50.py` against the index and every artifact.
The verifier must fail on a missing/extra logical artifact, schema error,
duplicate requirement finding, stale commit, digest mismatch, absolute path,
unknown required state, unapproved lowering, or documentation/evidence drift.
Engine-specific commands may produce evidence, but cannot replace the common
verifier or a real-backend release job.

## Canonical End-To-End Fixture

The same authored pipeline must run without engine-specific transformation
bodies:

```text
bounded source
  -> filter + projected/derived fields
  -> multi-input join
  -> grouped aggregate
  -> union + deterministic sort/deduplicate/limit
  -> contract validation
  -> normalized result
```

Separate focused fixtures cover every baseline function/operator, empty inputs,
all join and union modes, collisions, missing/invalid rejection, Unicode,
decimal/numeric boundaries, and declared materialization behavior. SQL fixtures
also record handle/fetch boundaries; PySpark records Catalyst plans; DataFusion
records native logical plans; DuckDB records accepted/rejected pushdown,
boundary explain output, and any collection, transfer, materialization, or lost
fusion effect. The same pushdown matrix runs against every baseline engine; its
expected result is manifest-driven and may be `not_applicable`, but every
declared boundary must still emit exactly one deterministic finding.

## Rollback Trigger And Procedure

Trigger rollback for any confirmed cross-engine semantic divergence, silent
native/engine fallback, SQL injection or early row fetch, Python UDF fallback in
the PySpark baseline, dependency leakage into core, nondeterministic result, or
secret/source-row leak.

1. Remove or downgrade the affected capability claim and fail closed for new
   plans; do not redirect work silently to another engine.
2. Invalidate cached plans whose selected compiler capability fingerprint has
   changed.
3. Preserve diagnostics and affected plan fingerprints without retaining source
   rows or secrets.
4. Restore the last passing compiler/runtime package combination or require an
   explicit native implementation body.
5. Update the published matrix and reopen the owning engine and cross-engine
   gate rows before restoring the claim.

## Go / No-Go

| Field | Record |
|---|---|
| Decision | **Pending independent Sol approval** |
| Approver | Sol final release gate |
| Review date | Pending |
| Technical outcome | All 28 scorecard rows and the canonical real-backend campaign pass; Luna does not grant release approval |
| Reproduction | `uv run python scripts/check_portable_0_50.py`; `uv run pytest`; `uv run pyright`; `uv run ruff check .`; `uv run ruff format --check .`; `uv run python scripts/check_release.py`; `uv build`; `uv run python scripts/check_docs.py` |
| Evidence | `docs/11_DEVELOPMENT/evidence/portable_0_50/portable_evidence_index_0_50.json` and its digest-bound artifact set |
| Limitations | Beta/community non-SLA; no common advanced, adaptive, streaming, remote, federated, or unqualified connector/sink claim |

#109 records the dated approval or rejection after Sol independently verifies
the repository. Missing or skipped evidence, any engine below the baseline,
any required applicable pushdown failure, misuse of `not_applicable`, or any
unresolved substantive finding is a no-go for the seven-engine
portable-baseline claim.

## Explicit Non-Claims

- No common advanced, window-frame, three-state, streaming, adaptive, remote,
  or federated syntax claim.
- No guarantee of identical physical types, plans, latency, memory use, or
  optimization across engines.
- No automatic fallback to native bodies, Python/Pandas UDFs, raw SQL, or a
  different engine.
- No maturity inheritance: one passing compiler, plugin, dialect, or fake does
  not qualify another.
