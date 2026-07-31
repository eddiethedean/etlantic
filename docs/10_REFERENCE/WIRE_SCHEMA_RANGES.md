# Wire schema ranges (through 0.36)

> **Status: Available in ETLantic 0.37.0.** Documents supported wire-schema
> ids for multi-minor burn-in and **unsupported downgrade** behavior. Package
> minors may advance while schema ids stay on `/1` (no wire-schema reset in
> 0.28–0.36).

## Compatibility vocabulary

Every burn-in matrix cell must use one of these outcomes:

| Outcome | Meaning |
|---|---|
| `compatible` | The reader accepts the artifact and preserves documented semantics |
| `migrated` | A versioned migration transforms the artifact without silent data loss |
| `regenerate` | The format is intentionally ephemeral; the user receives a documented deterministic regeneration path |
| `upgrade-required` | The older reader rejects a newer artifact with a stable actionable diagnostic |
| `unsupported` | The combination is outside the declared range and fails closed |

“Pass” means the observed result matches the declared contract — not that an
old reader always accepts a new artifact. Silent field loss, implicit
fallback, warning-only corruption, or a generic traceback is never a passing
outcome.

## Supported schema ranges

| Wire id | Package minors proven | Notes |
|---|---|---|
| `etlantic.pipeline/1` | 0.25 → 0.28 and 0.34 → 0.37 | Goldens under `tests/fixtures/burn_in/pipeline/v0_24/`–`v0_27/` and `v0_34/`–`v0_37/` |
| `etlantic.plan/1` | 0.25 → 0.28 and 0.34 → 0.37 | Goldens under `tests/fixtures/burn_in/plan/…` |
| `etlantic.run_report/1` | 0.25 → 0.28 and 0.34 → 0.37 | Goldens under `tests/fixtures/burn_in/run_report/…`; bare metadata keys migrate to namespaced keys in 0.37 |
| Profile JSON (no schema id) | 0.25 → 0.28 and 0.34 → 0.37 | Round-trip via `Profile.to_dict` / `from_dict` |
| `etlantic.capabilities/1` | 0.25 → 0.28 and 0.34 → 0.37 | Vocabulary major `/1`; see `vocabulary_major_compatible` |
| `etlantic.interchange/1` | 0.25 → 0.28 and 0.34 → 0.37 | Gate A tabular descriptors |
| `etlantic.authoring-catalog/1` | N/A (not burn-in versioned) | Stable schema id; catalog envelopes are tooling metadata, not burn-in upgrade artifacts — see [Surface inventory](SURFACE_INVENTORY.md) |
| `etlantic.quality/1` | 0.31+ (**provisional**) | Portable quality expressions; remains outside the full stable-foundation claim in 0.37; ContractModel remains semantic authority |
| `etlantic.scheduler/1` | 0.36+ (**stable MVP**) | Promoted onto the foundation path with Prefect-bounded evidence |

Upgrade hooks live in `etlantic.authoring.upgrade`, `etlantic.plan.upgrade`,
`etlantic.reports.upgrade`, and `etlantic.quality.upgrade`. Empty `_UPGRADERS`
maps mean the current `/1` document is accepted as-is (additive
compatibility). Intentional incompatible changes must register a documented
upgrader — **no silent field drops**.

## Historical quadruple-minor window (0.25 ↔ 0.28)

ETLantic 0.29 proved **four consecutive** minor upgrade paths without a
wire-schema reset:

1. **0.24 → 0.25** — fixtures under `*/v0_24/`
2. **0.25 → 0.26** — fixtures under `*/v0_25/`
3. **0.26 → 0.27** — fixtures under `*/v0_26/`
4. **0.27 → 0.28** — fixtures under `*/v0_27/`

Current codecs must continue to load and rewrite these golden trees.

## Joint burn-in window (0.34 ↔ 0.37)

ETLantic 0.37 proves the joint compatibility path:

1. **0.34 → 0.35** — fixtures under `*/v0_34/` and `*/v0_35/`
2. **0.35 → 0.36** — fixtures under `*/v0_35/` and `*/v0_36/`
3. **0.36 → 0.37** — fixtures under `*/v0_36/` and `*/v0_37/`
4. **0.35.0 known defect** — bare run-report metadata under
   `tests/fixtures/releases/v0_35/known_defects/` must `migrated` to
   namespaced keys

Release baseline manifests live under `tests/fixtures/releases/v0_34/`,
`v0_35/`, `v0_36/`, and `v0_37/`.

## Evidence gates (current-reader and isolated-wheel)

| Gate | Role |
|---|---|
| `scripts/check_pipeline_codec_burn_in.py` | Current-reader pipeline golden fingerprints |
| `scripts/check_codec_burn_in_matrix.py` | Current-reader sibling artifact digests |
| `scripts/check_isolated_codec_burn_in.py` | Isolated-wheel old/new writer→reader outcomes |
| `tests/authoring/test_pipeline_upgrade_burn_in.py` | Authoring upgrade burn-in |
| `tests/compatibility/test_codec_burn_in_matrix.py` | Compatibility matrix tests |

Current-reader gates are necessary but not sufficient for 0.37. Isolated-wheel
evidence must confirm declared outcomes using only public imports from the
writer and reader environments.

## Unsupported downgrade behavior

ETLantic does **not** silently downgrade documents:

| Attempt | Behavior |
|---|---|
| Unknown major (`…/99`, `…/2` before support) | Fail closed (`Unsupported*SchemaError` / descriptor error) |
| Missing required `schema` field | Fail closed |
| Hostile / secret-bearing payloads in pipeline JSON | Fail closed |
| Writing `/1` then reading with an older codec that lacks new optional fields | Older readers may ignore unknown optional keys only if they already did; 0.37 does not promise downgrade of **new required** fields |

There is **no** supported path to emit an older wire major from a newer runtime.
To move between package minors on the same `/1` id, use the burn-in fixtures and
[Migration 0.35 → 0.36](../11_DEVELOPMENT/MIGRATION_0_35_TO_0_36.md).

## See also

- [Compatibility](COMPATIBILITY.md)
- [Surface inventory](SURFACE_INVENTORY.md)
- [Protocol evolution](../07_PLUGIN_SDK/PROTOCOL_EVOLUTION.md)
- [Exit gate 0.36](../11_DEVELOPMENT/EXIT_GATE_0_36.md)
