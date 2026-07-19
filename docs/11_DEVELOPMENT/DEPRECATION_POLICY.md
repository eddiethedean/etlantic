# API Stability and Deprecation Policy

ETLantic is pre-1.0. Breaking changes remain possible, but they must not be
silent.

## Stability levels

| Surface | Current promise |
|---|---|
| Documented 0.14 public imports | Supported for the 0.14 line |
| Versioned plugin protocols | Compatible within their documented protocol version |
| Pipeline Plan schema | Governed by its schema version |
| Experimental APIs | May change in any 0.x release |
| Design proposals | No compatibility promise |
| Private underscore modules | No compatibility promise |

## Breaking-change requirements

A breaking 0.x change requires a changelog entry, migration guide, before/after
example, affected plugin/protocol analysis, and tests that make the new boundary
explicit. Persistent plans should normally be regenerated.

## Deprecation behavior

When practical, a replacement is documented and a warning is emitted for at
least one release before removal. Security fixes may shorten that window.
After 1.0, incompatible public API removal requires a major release unless a
documented security exception applies.

## Active 0.15 → 0.16 vocabulary deprecations

| Deprecated (0.15 warns) | Replacement | Removed |
|---|---|---|
| `Source` / `Sink` | `Extract` / `Load` | 0.16 |
| `binding=` on extract/load constructors | `asset=` | 0.16 |
| `.binding` property | `.asset` | 0.16 |
| `Profile(bindings=...)` / bindings-only JSON | `Profile(assets=...)` | 0.16 |
| `RunRequest.binding_overrides` | `asset_overrides` | 0.16 |

Wire names intentionally **not** deprecated: plan/graph `binding`,
`NodeKind` `"source"`/`"sink"`, DPCS `etlantic:binding`, plugin
`*_from_binding`, and port-wiring `Step.bindings`. See
[Migration 0.14 → 0.15](MIGRATION_0_14_TO_0_15.md).
