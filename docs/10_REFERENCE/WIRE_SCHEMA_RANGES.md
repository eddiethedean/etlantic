# Wire schema ranges (through 0.32; current package 0.32)

> **Status: Available in ETLantic 0.33.0.** Documents supported wire-schema
> ids for quadruple-minor burn-in and **unsupported downgrade** behavior. Package
> minors may advance while schema ids stay on `/1` (no wire-schema reset in
> 0.28–0.32).

## Supported schema ranges

| Wire id | Package minors proven | Notes |
|---|---|---|
| `etlantic.pipeline/1` | 0.25 → 0.26 → 0.27 → 0.28 | Goldens under `tests/fixtures/burn_in/pipeline/v0_24/` through `v0_27/` |
| `etlantic.plan/1` | 0.25 → 0.26 → 0.27 → 0.28 | Goldens under `tests/fixtures/burn_in/plan/v0_24/` through `v0_27/` |
| `etlantic.run_report/1` | 0.25 → 0.26 → 0.27 → 0.28 | Goldens under `tests/fixtures/burn_in/run_report/v0_24/` through `v0_27/` |
| Profile JSON (no schema id) | 0.25 → 0.26 → 0.27 → 0.28 | Round-trip via `Profile.to_dict` / `from_dict` |
| `etlantic.capabilities/1` | 0.25 → 0.26 → 0.27 → 0.28 | Vocabulary major `/1`; see `vocabulary_major_compatible` |
| `etlantic.interchange/1` | 0.25 → 0.26 → 0.27 → 0.28 | Gate A tabular descriptors |
| `etlantic.authoring-catalog/1` | N/A (not burn-in versioned) | Stable schema id; catalog envelopes are tooling metadata, not burn-in upgrade artifacts — see [Surface inventory](SURFACE_INVENTORY.md) |
| `etlantic.quality/1` | 0.31+ (provisional) | Portable quality expressions; no burn-in goldens required for first ship; ContractModel remains semantic authority |

Upgrade hooks live in `etlantic.authoring.upgrade`, `etlantic.plan.upgrade`,
`etlantic.reports.upgrade`, and `etlantic.quality.upgrade`. Empty `_UPGRADERS` maps mean the current `/1`
document is accepted as-is (additive compatibility). Intentional incompatible
changes must register a documented upgrader — **no silent field drops**.

## Quadruple-minor window (0.25 ↔ 0.28)

ETLantic 0.29 proves **four consecutive** minor upgrade paths without a
wire-schema reset:

1. **0.24 → 0.25** — fixtures under `*/v0_24/`
2. **0.25 → 0.26** — fixtures under `*/v0_25/`
3. **0.26 → 0.27** — fixtures under `*/v0_26/`
4. **0.27 → 0.28** — fixtures under `*/v0_27/`

Current codecs must load and rewrite all four golden trees. CI gates:
`scripts/check_pipeline_codec_burn_in.py` and
`scripts/check_codec_burn_in_matrix.py`.

## Unsupported downgrade behavior

ETLantic does **not** silently downgrade documents:

| Attempt | Behavior |
|---|---|
| Unknown major (`…/99`, `…/2` before support) | Fail closed (`Unsupported*SchemaError` / descriptor error) |
| Missing required `schema` field | Fail closed |
| Hostile / secret-bearing payloads in pipeline JSON | Fail closed |
| Writing `/1` then reading with a hypothetical older codec that lacks new optional fields | Older readers may ignore unknown optional keys only if they already did; 0.28 does not promise downgrade of **new required** fields |

There is **no** supported path to emit an older wire major from a newer runtime.
To move between package minors on the same `/1` id, use the burn-in fixtures and
[Migration 0.25 → 0.26](../11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md) /
[Migration 0.26 → 0.27](../11_DEVELOPMENT/MIGRATION_0_26_TO_0_27.md) /
[Migration 0.27 → 0.28](../11_DEVELOPMENT/MIGRATION_0_27_TO_0_28.md).

## CI gates

- `scripts/check_pipeline_codec_burn_in.py` — pipeline golden fingerprints (`v0_24` through `v0_27`)
- `scripts/check_codec_burn_in_matrix.py` — sibling artifact digests (`v0_24` through `v0_27`)
- `tests/authoring/test_pipeline_upgrade_burn_in.py`
- `tests/compatibility/test_codec_burn_in_matrix.py`

## See also

- [Compatibility](COMPATIBILITY.md)
- [Surface inventory](SURFACE_INVENTORY.md)
- [Protocol evolution](../07_PLUGIN_SDK/PROTOCOL_EVOLUTION.md)
