# Exit Gate 0.35 — Migration Completion and Joint Freeze (M7)

> **Status: Released.** ETLantic 0.35.0 was published to PyPI and GitHub
> on 2026-07-30 after the release checks below completed. This page records
> exit evidence; it is not the current capability reference.

| Deliverable | Status |
|---|---|
| Public `inspect_definition` / `rewrite_definition` / `definition_provenance` | Done |
| Application-pipeline testing preview (`etlantic.testing`) | Done (preview) |
| SparkForge project inventory scanner + migration report | Done |
| Safe native Medallantic definition generation | Done |
| Stable diagnostics for manual migration points (`MDL200`–`MDL230`) | Done |
| Golden before/after definition (+ plan where plannable) pairs | Done |
| Versioned deprecation timeline (adapters retained until major) | Done |
| Facade protocol/version + generated-definition provenance | Done |
| Joint exit evidence (no P0 parity gaps; wire schemas freeze-ready) | Done |
| Docs: What's New / Migration 0.34→0.35 / this exit gate | Done |

## Joint exit criteria

1. Both legacy builders (`pipeline_builder`, `sql_pipeline_builder`) have
   documented, tested migration paths — inventory + generate + goldens under
   `tests/medallantic/`.
2. Claimed parity rows remain backed by differential/conformance suites
   (`etlantic.testing.sparkforge_differential` /
   `sql_builder_differential`) plus M7 goldens.
3. Facade/core boundary and wire schemas (`pipeline/1`, `plan/1`) are
   freeze-ready; facade protocol version `1` + provenance extensions stamp
   generated definitions.
4. Testing preview proves validate → plan → run → report via public imports
   with explicit fixtures and no resolved secrets
   (`tests/testing/test_pipeline_case_preview_0_35.py`).

## Evidence map

| Gate item | Evidence |
|---|---|
| Authoring inspect/rewrite/provenance security | `tests/unit/test_authoring_inspect_0_35.py` |
| Testing preview (public imports) | `tests/testing/test_pipeline_case_preview_0_35.py` |
| Inventory + generate + CLI | `tests/medallantic/test_migration_inventory_0_35.py` |
| Golden corpus (both builders) | `tests/medallantic/test_migration_goldens_0_35.py` |
| CI medallantic job | `.github/workflows/checks.yml` → `tests/medallantic` |
| Deprecation timeline | `packages/medallantic/docs/sparkforge-migration.md` |

## Acceptance checklist

- [x] Authoring APIs secret-free / no untrusted import / no source rows
- [x] Inventory static-only (Python sources not executed)
- [x] Auto-safe IR generates provenance-stamped definitions
- [x] Manual/unsupported paths emit stable `MDL*` codes
- [x] Goldens for SparkForge + SQL builder IR
- [x] Testing preview succeeding + failing cases
- [x] No wire-schema reset for `pipeline/1` or `plan/1`
- [x] Transitional adapters retained (removal only on a future major)

## Residual / follow-ons (0.36+)

- Quantified joint upgrade burn-in (`0.34→0.35`, `0.35→0.36`) — **0.36**
- Application-pipeline testing foundation graduation — **0.38**
- Multi-tenant control plane — **0.40+**
- Removal of transitional SparkForge adapters — **major only**
