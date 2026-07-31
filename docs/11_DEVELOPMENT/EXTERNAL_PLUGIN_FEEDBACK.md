# External plugin feedback (Protocol `/1` freeze evidence)

> **Status:** Documents the ≥1 external feedback cycle required before claiming
> Plugin SDK `/1` **frozen** in **0.28.0**. Echo CI alone is insufficient per
> [Exit gate 0.22](EXIT_GATE_0_22.md). Revalidated against workspace core
> **0.39.0**; expected echo package floor is `etlantic>=0.39,<0.40` (workflow
> still installs `--no-deps` for forward-compat burn-in).

## Feedback cycle: `etlantic-plugin-echo`

| Field | Value |
|---|---|
| Plugin | [`etlantic-plugin-echo`](https://github.com/eddiethedean/etlantic-plugin-echo) |
| Maintainer | Out-of-monorepo reference author (not first-party engine code) |
| Date | 2026-07-30 (freeze evidence in 0.28; revalidated on 0.39.0; expected pin `etlantic>=0.39,<0.40`) |
| Surfaces exercised | `etlantic.dataframe/1`, public `etlantic.testing` conformance suites, plugin manifest + `etlantic plugin compatibility` |
| CI evidence | [`.github/workflows/external-plugin-echo.yml`](https://github.com/eddiethedean/etlantic/blob/main/.github/workflows/external-plugin-echo.yml) — weekly + on Plugin SDK path changes |
| Outcome | Public conformance suite green against workspace core; compatibility JSON report accepted without protocol drift |

### What was validated

1. **Packaging pin** — echo installs against workspace `etlantic` without
   monorepo-private imports.
2. **Conformance** — `pytest` in the echo repo using only public
   `etlantic.testing` helpers (no underscore modules).
3. **Compatibility CLI** — `etlantic plugin compatibility etlantic-plugin-echo`
   reports protocol `/1` alignment.

### Maintainer notes

- First-party plugins (polars, sql, pyspark, …) continue to exercise protocols
  in-repo; echo proves the **out-of-monorepo** author path.
- Storage / Resource / Observability protocol catalogs remain **future** work
  (post-freeze or a later 0.x phase) and are not part of this feedback cycle.

## 0.38 third-party connector proof (`038-X`)

| Field | Value |
|---|---|
| Selection | **`etlantic-plugin-echo`** (extend existing independent repo) |
| Planned surface | Source connector entry point (`etlantic.source_connectors`) + public `etlantic.testing` connector conformance |
| Status | Soft-continue — echo repo does not yet ship a connector EP |
| Finding | [`FINDINGS_0_38.md`](FINDINGS_0_38.md) open P1 `038-X-01` (ecosystem + echo maintainer) |
| Fallback | New stub repo only if echo cannot host the connector entry point |

Until echo adds a source connector, first-party proof remains
`local-files` + `scripts/check_connector_conformance.py --fake`.

## See also

- [Protocol evolution](../07_PLUGIN_SDK/PROTOCOL_EVOLUTION.md)
- [Building a plugin](../07_PLUGIN_SDK/BUILDING_A_PLUGIN.md)
- [Exit gate 0.28](EXIT_GATE_0_28.md)
- [Exit gate 0.29](EXIT_GATE_0_29.md)
