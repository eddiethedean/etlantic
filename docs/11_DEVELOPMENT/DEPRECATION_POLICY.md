# API Stability and Deprecation Policy

ETLantic 0.21.0 is stable for documented single-tenant reference deployments,
while remaining pre-1.0. Breaking changes remain possible, but they must not
be silent. See [Surface Inventory](../10_REFERENCE/SURFACE_INVENTORY.md).

## Stability levels

| Surface | Current promise |
|---|---|
| Documented 0.20 public imports | Supported for the 0.21.x line |
| Versioned plugin protocols | Compatible within their documented protocol version |
| Pipeline Plan schema | Governed by its schema version (`etlantic.plan/1`) |
| Experimental APIs | May change in any 0.x release |
| Design proposals | No compatibility promise |
| Private underscore modules | No compatibility promise |

## Pre-1.0 deprecation schedule (0.19 freeze)

| Surface | Status | Target |
|---|---|---|
| `DataContractModel` alias | provisional | remove or hard-error by 1.0 |
| Silent legacy profile `bindings` load | rejected (`PMCFG111`) unless `--accept-legacy-bindings` | done in 0.21 |
| Name/`security_domain` production heuristics | removed in 0.19 (`security_mode` only) | n/a |
| Missing wire `schema` defaults | removed in 0.19 | n/a |
| Ad hoc bare profile names | fail-closed; opt-in flag | keep flag through 1.0 |
| Structured Streaming | experimental | graduate or remain experimental at 1.0 |
| `etlantic-datafusion` | experimental | graduate only with measured advantage |
| Open plan metadata bare keys | warned (extension namespaces) | strict in production profiles (0.21) |
| Prefect scheduler MVP | provisional | expand or freeze protocol by 1.0 |

## Breaking-change requirements

A breaking 0.x change requires a changelog entry, migration guide, before/after
example, affected plugin/protocol analysis, and tests that make the new boundary
explicit. Persistent plans should normally be regenerated.

## Deprecation behavior

When practical, a replacement is documented and a warning is emitted for at
least one release before removal. Security fixes may shorten that window.
After 1.0, incompatible public API removal requires a major release unless a
documented security exception applies.

## Removed in 0.16 (authoring vocabulary)

| Removed | Replacement |
|---|---|
| `Source` / `Sink` | `Extract` / `Load` |
| `binding=` on extract/load constructors | `asset=` |
| `.binding` property | `.asset` |
| `Profile(bindings=...)` / mirrored public JSON `bindings` | `Profile(assets=...)` |
| `RunRequest.binding_overrides` | `asset_overrides` |

## Changed in 0.19 (configuration freeze)

| Change | Replacement / behavior |
|---|---|
| Production detection by name/domain | `Profile.security_mode == "production"` |
| Unknown bare profile names | Fail closed; `--allow-adhoc-profile` |
| Missing plan/report `schema` | Reject; no silent default |
| Nested plan mutation | Deep-frozen; fingerprint verify at trust boundaries |
