# Wire schema ranges (0.25)

> **Status: Available in ETLantic 0.25.1.** Documents supported wire-schema
> ids for burn-in and **unsupported downgrade** behavior. Package minors may
> advance while schema ids stay on `/1` (no wire-schema reset in 0.25).

## Supported schema ranges

| Wire id | Package minors proven | Notes |
|---|---|---|
| `etlantic.pipeline/1` | 0.24 → 0.25 | Golden fixtures under `tests/fixtures/burn_in/pipeline/v0_24/` |
| `etlantic.plan/1` | 0.24 → 0.25 | Golden fixtures under `tests/fixtures/burn_in/plan/v0_24/` |
| `etlantic.run_report/1` | 0.24 → 0.25 | Golden fixtures under `tests/fixtures/burn_in/run_report/v0_24/` |
| Profile JSON (no schema id) | 0.24 → 0.25 | Round-trip via `Profile.to_dict` / `from_dict` |
| `etlantic.capabilities/1` | 0.24 → 0.25 | Vocabulary major `/1`; see `vocabulary_major_compatible` |
| `etlantic.interchange/1` | 0.24 → 0.25 | Gate A tabular descriptors |

Upgrade hooks live in `etlantic.authoring.upgrade`, `etlantic.plan.upgrade`, and
`etlantic.reports.upgrade`. Empty `_UPGRADERS` maps mean the current `/1`
document is accepted as-is (additive compatibility). Intentional incompatible
changes must register a documented upgrader — **no silent field drops**.

## Unsupported downgrade behavior

ETLantic does **not** silently downgrade documents:

| Attempt | Behavior |
|---|---|
| Unknown major (`…/99`, `…/2` before support) | Fail closed (`Unsupported*SchemaError` / descriptor error) |
| Missing required `schema` field | Fail closed |
| Hostile / secret-bearing payloads in pipeline JSON | Fail closed |
| Writing `/1` then reading with a hypothetical older codec that lacks new optional fields | Older readers may ignore unknown optional keys only if they already did; 0.25 does not promise downgrade of **new required** fields |

There is **no** supported path to emit an older wire major from a newer runtime.
To move between package minors on the same `/1` id, use the burn-in fixtures and
[Migration 0.24 → 0.25](../11_DEVELOPMENT/MIGRATION_0_24_TO_0_25.md).

## CI gates

- `scripts/check_pipeline_codec_burn_in.py` — pipeline golden fingerprints
- `tests/authoring/test_pipeline_upgrade_burn_in.py`
- `tests/compatibility/test_codec_burn_in_matrix.py`

## See also

- [Compatibility](COMPATIBILITY.md)
- [Surface inventory](SURFACE_INVENTORY.md)
- [Protocol evolution](../07_PLUGIN_SDK/PROTOCOL_EVOLUTION.md)
