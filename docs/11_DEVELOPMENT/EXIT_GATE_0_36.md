# Exit Gate 0.36 — Joint Compatibility Burn-In

> **Status: Gate-ready for tag/publish rehearsal.** In-tree evidence for
> ETLantic and Medallantic **0.36.0** is green, including post-burn-in
> fail-closed hardenings recorded in CHANGELOG / Migration. This page does
> **not** claim that wheels are published to PyPI or that immutable Read the
> Docs pages are live. Tag and publish only after every P0 is closed and the
> scorecard below is green against the exact candidate artifacts.

| Deliverable | Status |
|---|---|
| Current-reader codec burn-in (`v0_24`–`v0_27`, `v0_34`–`v0_36`) | Done (local + CI gate) |
| Isolated-wheel old/new reader-writer harness | Done (local; CI step wired) |
| First-party plugin wheel conformance | Done (CI package job smokes) |
| Application-pipeline testing burn-in (preview freeze) | Done (local corpus tests) |
| Medallantic joint burn-in | Done (hard-gate tests + existing differentials) |
| `scheduler/1` stable MVP decision + Prefect bounds | Done |
| `quality/1` remains provisional (documented) | Done |
| Run-report bare → namespaced metadata migration | Done |
| Docs: What's New / Migration 0.35→0.36 / this exit gate / findings | Done |
| Immutable `/en/v0.36.0/` docs + published wheels | Not started (pre-publish; do not tag until asked) |

## Quantified exit scorecard

From [IMPLEMENTATION_PLAN_0_36](IMPLEMENTATION_PLAN_0_36.md):

| Measure | Required | Current |
|---|---:|---|
| Supported wire-schema/protocol matrix cells with executable evidence | 100% | Done (local + CI gates) |
| First-party plugins passing applicable public conformance from wheels | 100% | Done (CI package job) |
| Required application-case/engine cells passing | 100% | Done (engine CI jobs) |
| Unexplained Medallantic semantic differences | 0 | Done (hard-gated differentials) |
| Unversioned wire-schema changes | 0 | Done (no reset) |
| Resolved secret values in retained artifacts | 0 | Done (fail-closed suites) |
| Production plugin paths that bypass allowlist/compatibility checks | 0 | Done (pin + canonicalize hardenings) |
| Unresolved P0 findings | 0 | Done — see [FINDINGS_0_36](FINDINGS_0_36.md) |
| Remaining P1 findings without owner, phase, mitigation, and rationale | 0 | Done (ledger has no open P1) |
| Release-facing immutable documentation URLs returning non-200 | 0 | Pre-publish |
| Runnable documentation claims without executed CI evidence | 0 | Done (docs + CI gates) |

## Evidence map

| Gate item | Evidence |
|---|---|
| Current-reader pipeline goldens | `scripts/check_pipeline_codec_burn_in.py` |
| Current-reader sibling artifact matrix | `scripts/check_codec_burn_in_matrix.py` |
| Isolated-wheel reader/writer matrix | `scripts/check_isolated_codec_burn_in.py` |
| Release baselines / known defects | `tests/fixtures/releases/` (`v0_34/`, `v0_35/`, `v0_36/`; bare-key defect under `v0_35/known_defects/`) |
| Burn-in goldens | `tests/fixtures/burn_in/` (`v0_24`–`v0_27`, `v0_34`–`v0_36`) |
| Codec / upgrade compatibility tests | `tests/compatibility/`, `tests/authoring/` |
| Application-pipeline testing preview / burn-in | `tests/testing/` |
| Medallantic migration, goldens, differentials | `tests/medallantic/` |
| Protocol freeze automation | `scripts/check_protocol_freeze.py` |
| Finding severity / locked decisions | [FINDINGS_0_36.md](FINDINGS_0_36.md) |
| Adopter migration | [MIGRATION_0_35_TO_0_36.md](MIGRATION_0_35_TO_0_36.md) |
| Adopter highlights | [WHATS_NEW_0_36.md](../01_GETTING_STARTED/WHATS_NEW_0_36.md) |

## Acceptance checklist

### Compatibility harness

- [x] Burn-in fixture trees exist for `v0_34`, `v0_35`, and `v0_36`
- [x] Historical `v0_24`–`v0_27` current-reader gates remain documented
- [x] Release manifests under `tests/fixtures/releases/`
- [x] 0.35.0 bare-key report defect fixture recorded
- [x] `scripts/check_pipeline_codec_burn_in.py` green on candidate
- [x] `scripts/check_codec_burn_in_matrix.py` green on candidate
- [x] `scripts/check_isolated_codec_burn_in.py` green (isolated old/new wheels)
- [x] Every supported matrix cell has a declared outcome
  (`compatible` / `migrated` / `regenerate` / `upgrade-required` /
  `unsupported`)

### Packages and protocols

- [x] `scheduler/1` promoted to stable MVP (Prefect bounds) — decision locked
- [x] `quality/1` retained as provisional outside full foundation claim
- [x] Testing preview minimum contract frozen for burn-in (graduation = 0.37)
- [x] All thirteen distributions build from the same candidate commit (CI package job)
- [x] First-party plugins pass applicable public conformance from clean wheels
- [x] Production allowlist / digest / incompatible-protocol paths fail closed
- [x] Production allowlist null/empty pins fail closed (`PMPLUG403`); package
  names canonicalized
- [x] Safe I/O empty roots / symlink reject / authoring secret denylist /
  schema-history row guards / outbound production default-deny hardened
- [x] Missing implementations fail at plan (`PMPLAN301`); CONTINUE soft-skips
  report `PARTIAL`
- [x] Core wheel Quickstart runs without engine/orchestrator deps

### Application and Medallantic burn-in

- [x] Canonical application cases pass across local advertised intersection
  (Polars/Pandas/SQL/PySpark continue via existing engine CI jobs)
- [x] Airflow deterministic compile-from-plan evidence (existing airflow CI)
- [x] Prefect bounded scheduler cases for stable MVP
- [x] Medallantic definition + migration-IR evidence (existing goldens + hard gates)
- [x] SparkForge and SQL-builder differentials: zero unexplained differences
  (existing differential suites remain hard-gated)
- [x] Transitional adapters retained (no removal in 0.36)
- [x] No medallion layer types enter ETLantic core

### Security and release

- [x] Zero resolved secrets in plans, reports, diagnostics, snapshots, fixtures
- [x] Hostile / oversized / unknown-version fixtures fail closed
- [x] Unresolved P0 count is **0** ([FINDINGS_0_36](FINDINGS_0_36.md))
- [x] Every remaining P1 has owner, target phase, mitigation, rationale
  (none open; ledger empty)
- [ ] SHA-256 digests, package metadata, and attestations rehearsed at tag time
- [ ] Immutable `/en/v0.36.0/` docs return HTTP 200 before announcement
- [ ] Tag/publish only after the scorecard is green (not claimed yet)

## Residual / follow-ons

- **0.37** — stable foundation: release rehearsal, application-pipeline
  testing foundation graduation; remaining
  provisional surfaces dispositioned for the stable foundation
- Multi-tenant control plane — **0.39+**
- Removal of transitional SparkForge adapters — **major only**
