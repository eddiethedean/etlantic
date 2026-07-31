# Migration 0.34 → 0.35

> **Status: Available in ETLantic 0.35.0.** Migration completion / joint freeze
> (M7); **no wire-schema reset** (`etlantic.plan/1` / `pipeline/1` unchanged).

## Summary

| Area | Change |
|---|---|
| Wire schemas | Still `pipeline/1`, `plan/1`, … |
| Package pin | `etlantic==0.35.0`; plugins / `medallantic==0.35.0` |
| Authoring | Public `inspect_definition`, `rewrite_definition`, `definition_provenance` |
| Testing | Application-pipeline testing **preview** in `etlantic.testing` |
| Medallantic | Project inventory scanner, safe native generation, migration diagnostics |
| Deprecation | Legacy SparkForge / `etlantic-sparkforge` timeline published; adapters retained until a major |

## Upgrade steps

1. Pin core and matching plugins:

   ```bash
   python -m pip install --upgrade 'etlantic==0.35.0'
   python -m pip install --upgrade 'medallantic==0.35.0'
   ```

2. Re-validate and re-plan pipelines after the pin bump.

3. Optional: adopt `etlantic.testing` pipeline-case helpers for local fixtures
   (preview API — not the 0.37 graduated foundation).

4. Optional: run Medallantic inventory against SparkForge projects before
   converting definitions:

   ```bash
   python -m medallantic migrate inventory PATH
   python -m medallantic migrate generate path/to/ir.json
   ```

## Breaking changes

- Plugin dependency floor becomes `etlantic>=0.35.0,<0.36`.
- No intentional wire-schema break; treat any unexpected plan/report shape
  change as a bug.

## Deprecation timeline (adapters retained)

| Surface | 0.35 status | Removal |
|---|---|---|
| `medallantic.migrate.sparkforge` / `.sql` | Supported | Not before a documented **major** |
| `etlantic-sparkforge` shim package | Supported | Not before a documented **major** |
| Serialized SparkForge IR shapes | Supported | Not before a documented **major** |
| Live builder bridges | Supported when legacy deps installed | Not before a documented **major** |

0.35 does **not** remove transitional adapters.

## Rollback

Re-pin `etlantic==0.34.0` and matching `0.34.0` plugins / `medallantic==0.34.0`,
then re-validate. Do not mix 0.34 and 0.35 minors in one environment.

## Security notes

Migration inventory and analysis paths must not resolve secrets, import
untrusted code, read source rows, or mutate targets. Review release digests
and attestations as for any release.
