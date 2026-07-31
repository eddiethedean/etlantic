# Exit Gate 0.37 — Stable Foundation

> **Status: Gate-ready for tag/publish rehearsal.** In-tree evidence for
> ETLantic and Medallantic **0.37.0** is green (acceptance 21/21, removals,
> security matrix, freeze inventories). This page does **not** claim that
> wheels are published to PyPI or that immutable Read the Docs pages are live.
> Tag and publish only after every P0 is closed and the scorecard below is
> green against the exact candidate artifacts.

| Deliverable | Status |
|---|---|
| Planning: implementation plan / this exit gate / findings / What's New / migration | Done |
| Removals: demoted root aliases + `DataContractModel` | Done (executed in-tree; see [REMOVAL_CANDIDATES_0_37](REMOVAL_CANDIDATES_0_37.md)) |
| Testing foundation graduation (`etlantic.testing`) | Done (local evidence; isolated-wheel path documented) |
| Acceptance suite items 1–21 | Done (`tests/stable_foundation/` + `scripts/check_stable_foundation.py`; 21/21) |
| Security verification matrix | Done |
| Stability freeze inventories + plugin floor `>=0.37,<0.38` | Done (surface / protocol / diagnostic tiers; first-party floor declared) |
| Release rehearsal (wheels, digests, immutable docs) | In progress (in-repo fixtures + local `uv build`; digests at tag) |
| Immutable `/en/v0.37.0/` docs + published wheels | Not started |

## Quantified exit scorecard

From [IMPLEMENTATION_PLAN_0_37](IMPLEMENTATION_PLAN_0_37.md):

| Measure | Required | Current |
|---|---:|---|
| Acceptance suite items 1–21 with executable evidence (or explicit non-blocking disposition) | 100% | Met — 21/21 (`scripts/check_stable_foundation.py`) |
| Demoted root aliases remaining on public root | 0 | Met (`_DEMOTED_ALIASES` empty; `_REMOVED_0_37` raises) |
| `DataContractModel` still importable as public alias | 0 | Met (removed; AttributeError guidance) |
| Testing graduation gates met (public imports, isolated wheel, redaction) | 100% | Met in-repo (`tests/testing/`); isolated-wheel via burn-in script path |
| Security matrix controls with owner + automated verification | 100% | Met (`docs/02_FOUNDATIONS/SECURITY_VERIFICATION_MATRIX.md` + `scripts/check_security_matrix.py`) |
| Resolved secret values in retained artifacts | 0 | Met (fail-closed suites + fixture review) |
| Production plugin paths that bypass allowlist/compatibility checks | 0 | Met (carry-forward 0.36 hardenings; re-verified in 0.37 suites) |
| Unresolved P0 findings | 0 | Met — see [FINDINGS_0_37](FINDINGS_0_37.md) |
| Remaining P1 findings without owner, phase, mitigation, and rationale | 0 | Met (open ledger empty) |
| Unversioned wire-schema changes | 0 | Met (no reset; burn-in `v0_34`–`v0_37` current-reader green) |
| Release-facing immutable documentation URLs returning non-200 | 0 | Not started (post-tag RTD activate/build) |
| Runnable documentation claims without executed CI evidence | 0 | Met (docs + CI gates) |

## Evidence map

| Gate item | Evidence |
|---|---|
| Aggregated stable-foundation gate | `scripts/check_stable_foundation.py` |
| Acceptance corpus / fixtures | `tests/stable_foundation/` |
| Testing graduation | `tests/testing/` (+ isolated-wheel proofs under stable-foundation) |
| Removals / demoted aliases | `src/etlantic/__init__.py`; removal tests; [REMOVAL_CANDIDATES_0_37](REMOVAL_CANDIDATES_0_37.md) |
| Security verification matrix | `docs/02_FOUNDATIONS/SECURITY_VERIFICATION_MATRIX.md` (+ `security-verification-matrix.json`; CI `scripts/check_security_matrix.py`) |
| Security / trust / redaction suites | `tests/` security, secrets, plugin-trust, safe-I/O paths |
| Protocol / surface freeze | `scripts/check_protocol_freeze.py`; `scripts/check_surface_inventory.py`; [SURFACE_INVENTORY](../10_REFERENCE/SURFACE_INVENTORY.md) |
| Diagnostic-code stability tiers | `scripts/check_diagnostic_stability.py`; [DIAGNOSTIC_STABILITY_TIERS](../10_REFERENCE/DIAGNOSTIC_STABILITY_TIERS.md) |
| Compatibility burn-in carry-forward | `scripts/check_pipeline_codec_burn_in.py`, `scripts/check_codec_burn_in_matrix.py`, `scripts/check_isolated_codec_burn_in.py` |
| Release baselines | `tests/fixtures/releases/v0_37/` |
| Finding severity / locked decisions | [FINDINGS_0_37.md](FINDINGS_0_37.md) |
| Adopter migration | [MIGRATION_0_36_TO_0_37.md](MIGRATION_0_36_TO_0_37.md) |
| Adopter highlights | [WHATS_NEW_0_37.md](../01_GETTING_STARTED/WHATS_NEW_0_37.md) |
| Prior burn-in exit | [EXIT_GATE_0_36.md](EXIT_GATE_0_36.md) |

## Acceptance checklist

### Planning

- [x] [IMPLEMENTATION_PLAN_0_37](IMPLEMENTATION_PLAN_0_37.md) published
- [x] This exit gate published (status: Gate-ready for tag/publish rehearsal)
- [x] [FINDINGS_0_37](FINDINGS_0_37.md) ledger opened
- [x] [WHATS_NEW_0_37](../01_GETTING_STARTED/WHATS_NEW_0_37.md) published
- [x] [MIGRATION_0_36_TO_0_37](MIGRATION_0_36_TO_0_37.md) published
- [x] Indexes / roadmap / mkdocs point at 0.37 as current gate

### Removals

- [x] Remaining `_DEMOTED_ALIASES` removed from public root
- [x] `DataContractModel` removed (use `ContractModel` / `Data`)
- [x] CHANGELOG + migration list every removal
- [x] [REMOVAL_CANDIDATES_0_37](REMOVAL_CANDIDATES_0_37.md) Target columns updated to executed

### Testing graduation

- [x] Public `etlantic.testing` case/result/snapshot contract documented as stable
- [x] Cross-engine cases pass advertised intersection
- [x] Fault / cancellation / unknown-effect fakes require no production system
- [x] Snapshot updates are explicit, reviewable, redacted, and size-bounded
- [x] Isolated-wheel example uses public imports only
  (evidence path: `scripts/check_isolated_codec_burn_in.py`; public-import AST
  gate in `tests/testing/test_testing_foundation_0_37.py`)
- [x] Independently maintained application CI uses the public testing API
  (`.github/workflows/checks.yml` runnable `examples/memory_customers.py` +
  public `PipelineTestCase` coverage in `tests/testing/`)

### Acceptance suite 1–21

- [x] Items 1–13 have executable evidence (`test_sf_01` … `test_sf_13`; engines `importorskip`)
- [x] Item 14 Arrow boundary: Gate A only (diagnosed fallback; no Gate B claim) — `test_sf_14`
- [x] Item 15 DataFusion: explicit experimental / non-blocking disposition — `test_sf_15` + script disposition
- [x] Items 16–21 have executable evidence (`test_sf_16` … `test_sf_21`)
- [x] `scripts/check_stable_foundation.py` wired (AST coverage + `pytest tests/stable_foundation`)
- [x] `tests/stable_foundation/` corpus reviewed and secret-free (candidate freeze)

### Security and freeze

- [x] `docs/02_FOUNDATIONS/SECURITY_VERIFICATION_MATRIX.md` links owner + automated check per control
- [x] Zero resolved secrets in plans, reports, diagnostics, snapshots, fixtures
- [x] Production allowlist / digest / incompatible-protocol paths fail closed
- [x] Stability inventories match claimed surface; plugin floor `>=0.37,<0.38`
  (`surface-inventory.json`, diagnostic tiers, protocol freeze; first-party
  packages declare `etlantic>=0.37.0,<0.38`)
- [x] Beta classifier retained on core and first-party packages
- [x] `scheduler/1` remains stable MVP; `quality/1` remains provisional;
  `etlantic.testing` graduated stable

### Release

- [x] Unresolved P0 count is **0** ([FINDINGS_0_37](FINDINGS_0_37.md))
- [x] Every remaining P1 has owner, target phase, mitigation, rationale
  (`037-REL-PYPI`, `037-REL-RTD`, `037-REL-ECHO-PIN` — release maintainers;
  close at tag/publish / RTD activate / echo-repo pin bump)
- [ ] SHA-256 digests, package metadata, and attestations rehearsed
  (local `uv build` OK; digests/attestations at tag workflow)
- [ ] Immutable `/en/v0.37.0/` docs return HTTP 200 before announcement
- [ ] Tag/publish completed only after scorecard is green

## Locked dispositions (summary)

| Surface | Disposition |
|---|---|
| Testing | Graduates |
| `quality/1` | Provisional |
| DataFusion | Experimental |
| Arrow | Gate A only |
| Demoted aliases + `DataContractModel` | Removed in 0.37.0 |
| Scheduler | Already stable MVP (0.36; unchanged in 0.37) |
| Beta classifier | Retained |

## Residual / follow-ons

- **`037-REL-PYPI`** — tag/publish so PyPI serves `0.37.0` (+ digests/attestations)
- **`037-REL-RTD`** — activate/build immutable `/en/v0.37.0/` after tag
- **`037-REL-ECHO-PIN`** — raise external `etlantic-plugin-echo` floor to
  `etlantic>=0.37,<0.38` (workflow already documents the expected pin and
  installs `--no-deps`)
- Multi-tenant control plane — **0.39+**
- Data connectivity / connector SDK — **0.38**
- Removal of transitional SparkForge adapters — **major only**
- `etlantic.quality/1` full foundation claim — later explicit graduation only
- DataFusion Gate B — only after measured conformance; not part of 0.37
