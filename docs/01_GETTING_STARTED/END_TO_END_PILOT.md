# End-to-end pilot

> **Status: Available in ETLantic 0.40.0.** Pip-only walkthrough from `init`
> through reshape, optional quality, SARIF validate, run, and `report query`.
> No repository clone required.

!!! tip "PyPI only"
    This page continues [Quickstart](QUICKSTART.md) / [First Pipeline](FIRST_PIPELINE.md).
    Prefer it when you want one path that ends in CI evidence and durable reports.

## 1. Install and scaffold

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install 'etlantic==0.40.0'
mkdir my-pipeline && cd my-pipeline
python -m etlantic init --with-toml
```

Confirm `python -m etlantic --version` prints `0.40.0`.

## 2. Reshape transform

Replace the scaffold passthrough with the upper-case reshape from
[First Pipeline](FIRST_PIPELINE.md#evolve-the-transform) (`UpperName` /
`NamedRow`). Re-validate and run:

```bash
python -m etlantic validate pipeline.py:SamplePipeline \
  --profile development --format json
python -m etlantic run pipeline.py:SamplePipeline --profile development
```

Expect `succeeded` and `"ADA"` / `"GRACE"` in `data/out.json`.

## 3. Optional quality gate

Portable quality (`etlantic.quality` / `make_quality_gate`) is available on
local / Polars / Pandas paths; SQL and PySpark still fail closed for portable
quality compilers. For this pilot you may skip quality and continue, or add a
gate after reading [API — Quality](../10_REFERENCE/API_QUALITY.md) and
[What's new in 0.30](WHATS_NEW_0_30.md).

## 4. Validate as SARIF (CI evidence)

```bash
python -m etlantic validate pipeline.py:SamplePipeline \
  --profile development --format sarif > etlantic.sarif
```

Copy the same command into PR CI. Full workflow:
[CI integration](../06_EXECUTION/CI_INTEGRATION.md).

## 5. Run and query reports

Default `run` writes under `.etlantic/reports/` (durable unless `--ephemeral`):

```bash
python -m etlantic run pipeline.py:SamplePipeline --profile development
python -m etlantic report list
python -m etlantic report query --status succeeded --limit 5 --format json
```

See [Reports and history](../06_EXECUTION/REPORTS_AND_HISTORY.md).

## Next

- [Production profiles](../06_EXECUTION/PRODUCTION_PROFILES.md) — allowlisted pilot profile
- [Ops pilot](../06_EXECUTION/OPS_PILOT.md) / [Production readiness](../06_EXECUTION/PRODUCTION_READINESS.md)
- [Rollback and recovery](../06_EXECUTION/ROLLBACK_RECOVERY.md)
