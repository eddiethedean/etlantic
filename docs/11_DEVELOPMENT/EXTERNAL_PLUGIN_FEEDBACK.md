# External plugin feedback (Protocol `/1` freeze evidence)

> **Status:** Documents the ≥1 external feedback cycle required before claiming
> Plugin SDK `/1` **frozen** in **0.28.0**. Echo CI alone is insufficient per
> [Exit gate 0.22](EXIT_GATE_0_22.md). Revalidated against workspace core
> **0.31.0** after the echo package pin refresh.

## Feedback cycle: `etlantic-plugin-echo`

| Field | Value |
|---|---|
| Plugin | [`etlantic-plugin-echo`](https://github.com/eddiethedean/etlantic-plugin-echo) |
| Maintainer | Out-of-monorepo reference author (not first-party engine code) |
| Date | 2026-07-28 (freeze evidence in 0.28; revalidated on 0.31.0) |
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
  (post-freeze or 1.x) and are not part of this feedback cycle.

## See also

- [Protocol evolution](../07_PLUGIN_SDK/PROTOCOL_EVOLUTION.md)
- [Building a plugin](../07_PLUGIN_SDK/BUILDING_A_PLUGIN.md)
- [Exit gate 0.28](EXIT_GATE_0_28.md)
- [Exit gate 0.29](EXIT_GATE_0_29.md)
