# Exit Gate 0.24 — Programmatic Authoring and Lossless JSON

| Deliverable | Status |
|---|---|
| Canonical `PipelineDefinition` + class normalizer | Done |
| `etlantic.pipeline/1` codecs, schema, fingerprints, Safe I/O | Done |
| Functional builders + class/functional/JSON parity | Done |
| Lifecycle on definitions (validate/plan/run/inspect) | Done |
| CLI JSON TARGET + `generate --kind definition` | Done |
| Authoring catalog + EditCommand + visual-builder fixture | Done |
| Service facade + `etlantic-fastapi` reference adapter | Done |
| Docs: What's New / Migration / this exit gate | Done |
| Core + plugins bumped to 0.24.0 | Done |

## Acceptance checklist

- [x] Author/run multi-source multi-output parameterized pipelines without classes (`tests/authoring/`)
- [x] Class ↔ functional parity fingerprints (`test_definition_codecs.py`)
- [x] Byte-stable `pipeline → JSON → PipelineDefinition → JSON` round trips
- [x] Deserialized definition validates/plans/runs without originating class
- [x] Hostile/unknown/secret payloads fail closed
- [x] CLI accepts definition JSON TARGET; SDK/CLI export via `generate --kind definition`
- [x] Visual-builder public-API fixture (`test_visual_builder_fixture.py`)
- [x] FastAPI/OpenAPI reference (`packages/etlantic-fastapi`)
- [x] Wire inventory lists `etlantic.pipeline/1` and authoring catalog

## Residual / follow-ups (0.25+)

- Compatibility burn-in for `etlantic.pipeline/1` upgrade fixtures
- Production FastAPI Control API (1.1)
- Broader functional parity matrix for every class primitive edge case
- Nested subpipeline edit UX polish
