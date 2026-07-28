# Best Practices

> **Status: Available in ETLantic 0.31.0.** Adopter-facing habits for safe,
> inspectable pipelines. Prefer this over scattered “best practices” asides.

## Authoring

1. Use public imports: `etlantic`, `etlantic.dataframe`, `.sql`, `.spark`,
   `.orchestration`, `.viz`, `.secrets`, `.testing`.
2. Prefer `Extract` / `Load` vocabulary—not legacy Source/Sink names.
3. Keep transformations as contracts (`Transformation` + ports) with separate
   `@implementation(...)` or `@portable` bodies.
4. Validate before plan/compile/run: `etlantic validate TARGET --format json`.

## Profiles and trust

1. Use named profiles (`development` / `test` / production JSON). Prefer an
   explicit `--profile` in CI.
2. Production profiles require a non-empty `plugin_allowlist` with exact pins.
3. Set `security_mode` explicitly (`development` | `test` | `production`).
4. Pin matching minors: `etlantic==0.31.0` with `etlantic-polars==0.31.0`, etc.

## Secrets and artifacts

1. Plans and reports must contain secret **references**, never resolved values.
2. Resolve secrets at runtime from env, mounted files, or `etlantic-keyring`.
3. Schema history stores fingerprints/metadata only—never source rows.
4. Treat `.etlantic/reports/` as operational evidence, not a compliance SoR.

## CLI workflow

```bash
python -m etlantic doctor --profile development
python -m etlantic validate TARGET --profile development --format json
python -m etlantic plan TARGET --profile development --format json
python -m etlantic run TARGET --profile development          # durable assets
python -m etlantic validate TARGET --format sarif            # CI
```

Start from `etlantic init` for JSON-backed assets so CLI `run` works without
memory seeding. Use in-memory demos only inside one Python process.

## Anti-patterns (and what happens)

1. **Empty production allowlist** — `security_mode="production"` with
   `plugin_allowlist: {}` fails closed (`PMPLUG401`). Copy
   [prod.example.json](prod.example.json) and pin exact plugin versions.
2. **Root imports removed in 0.28** — importing `load_profile` or `col` from the
   package root raises `AttributeError`. Prefer
   `etlantic.profile.load_profile` / `etlantic.sql.col`
   (see [Migration 0.27 → 0.28](../11_DEVELOPMENT/MIGRATION_0_27_TO_0_28.md)).
3. **Validate on one profile, run on another** — assets/engines diverge and
   failures look like “random” runtime errors. Pass the same `--profile` for
   validate, plan, and run.
4. **Skip validate after a contract edit** — wiring errors surface as
   `PMPIPE*` on validate; running first may write nothing useful or fail late.

## Failed validate / run stories

| Symptom | Likely cause | Fix |
|---|---|---|
| `PMPIPE210` (or wiring diagnostic) after editing Load | Load contract ≠ upstream Output | Restore matching `Load[T]` or change the transform Output |
| `PMPLUG401` on production profile | Empty allowlist | Pin plugins in profile JSON |
| `ModuleNotFoundError: pipeline` after Quickstart SDK snippet | Wrong cwd | `cd` to the `init` project root |
| Validate green, run has no rows | In-memory assets without seed | Use JSON/CSV assets from `init`, or seed via `PipelineRuntime.memory` |

## CI

1. Fail the build on validate errors (JSON or SARIF).
2. Re-plan after profile or plugin changes; store plan fingerprints when useful.
3. Compile Airflow only from a valid plan (`etlantic-airflow`).

## Engines

1. Prove one engine path under validate/plan before combining engines.
2. Keep a native `@implementation(...)` for portable profiles outside the
   advertised claim set, or use `portable_transform_policy="native"`.

## Related

- [Cookbook](COOKBOOK.md)
- [Production readiness](../06_EXECUTION/PRODUCTION_READINESS.md)
- [Production profiles](../06_EXECUTION/PRODUCTION_PROFILES.md)
- [Evaluator brief](EVALUATOR.md)
- [Security](../02_FOUNDATIONS/SECURITY.md)
