# API Stability and Deprecation Policy

ETLantic 0.40.0 is a Beta (PyPI) release suitable for documented single-tenant
pilots—not unrestricted enterprise production. The roadmap remains entirely
within the 0.x series; **0.37** is the stable-foundation gate (in-tree
gate-ready; tag/publish separate). Breaking
changes remain possible, but they must not be silent. See
[Surface Inventory](../10_REFERENCE/SURFACE_INVENTORY.md).

## Stability levels

| Surface | Current promise |
|---|---|
| Documented 0.40 public imports | Supported for the 0.40.x line |
| Versioned plugin protocols | Compatible within their documented protocol version |
| Pipeline Plan schema | Governed by its schema version (`etlantic.plan/1`) |
| Experimental APIs | May change in any 0.x release |
| Design proposals | No compatibility promise |
| Private underscore modules | No compatibility promise |

## 0.x deprecation schedule (0.19 freeze)

See [freeze glossary](../07_PLUGIN_SDK/PROTOCOL_EVOLUTION.md#freeze-glossary-three-different-terms)
— this is the **contract/configuration freeze**, not protocol `/1` freeze or
full plan object-graph immutability.

| Surface | Status | Target |
|---|---|---|
| `DataContractModel` alias | **removed in 0.37.0** | use `ContractModel` / `Data` |
| Silent legacy profile `bindings` load | rejected (`PMCFG111`) unless `--accept-legacy-bindings` | done in 0.21 |
| Name/`security_domain` production heuristics | removed in 0.19 (`security_mode` only) | n/a |
| Missing wire `schema` defaults | removed in 0.19 | n/a |
| Ad hoc bare profile names | fail-closed; opt-in flag | keep flag through 0.37 |
| Structured Streaming | experimental | graduate in 0.46 or remain experimental |
| `etlantic-datafusion` | experimental | graduate only with measured advantage |
| Open plan metadata bare keys | warned (extension namespaces) | strict in production profiles (0.21) |
| Prefect scheduler MVP | **frozen as `scheduler/1` stable MVP** (0.36) | Prefect bounds unchanged; no further expand-or-freeze gate in 0.37 |
| Demoted root aliases (`_DEMOTED_ALIASES`) | first wave 0.26.0; second 0.27.0; third **0.28.0**; remainder **removed in 0.37.0** | empty; see [Removal candidates](REMOVAL_CANDIDATES_0_37.md) |

### 0.x burn-in discipline (0.28 line)

Do **not** add new indefinite keep-forever root aliases while ETLantic is on
the 0.29 burn-in line. Prefer owning modules or the curated root facade.

Third-wave removals in **0.28.0** (import from owning modules):

- `etlantic.sql` — `RelationRef`, `SqlQuery`, `col`, `concat`, `select`,
  `discover_sql_plugins`
- `etlantic.profile` — `development_profile`, `load_profile`,
  `production_profile`, `resolve_profile`, `test_profile`, `write_profile`
- `etlantic.lifecycle` — `Emit`, `FailureAction`, `Inject`, `OutboundEvent`,
  `StepFailureContext`

See [Migration 0.27 → 0.28](MIGRATION_0_27_TO_0_28.md).

## Breaking-change requirements

A breaking 0.x change requires a changelog entry, migration guide, before/after
example, affected plugin/protocol analysis, and tests that make the new boundary
explicit. Persistent plans should normally be regenerated.

## Deprecation behavior

When practical, a replacement is documented and a warning is emitted for at
least one release before removal. Security fixes may shorten that window.
After the 0.38 stable-foundation freeze, an incompatible public API removal
requires an explicitly scheduled 0.x migration phase and documented
deprecation window unless a security exception applies.

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
| Nested plan mutation | Nested mappings/lists/sets frozen via `deep_freeze` (not full object graphs); fingerprint verify at trust boundaries. See [freeze glossary](../07_PLUGIN_SDK/PROTOCOL_EVOLUTION.md#freeze-glossary-three-different-terms). |
