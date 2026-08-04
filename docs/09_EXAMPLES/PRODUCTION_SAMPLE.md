# Production sample pilot

> **Status: Available in ETLantic 0.44.0.** Clone companion under
> `examples/sample_pilot/`. Demonstrates a production profile
> (`security_mode=production` + allowlist), file I/O, SARIF validate,
> and optional Airflow compile.

## PyPI path (no clone)

```bash
python -m pip install 'etlantic[polars]==0.44.0'
mkdir pilot && cd pilot
python -m etlantic init --with-toml
```

Add a Polars implementation (see [Polars tutorial](../06_EXECUTION/POLARS_TUTORIAL.md)),
then write `profiles/prod.json` (trim `plugin_allowlist` to packages you
actually installed — a monorepo with every plugin installed must allowlist
each discovered package or validation fails with `PMPLUG402`):

```json
{
  "name": "pilot-prod",
  "security_mode": "production",
  "security_domain": "production",
  "orchestrator": "local",
  "dataframe_engine": "polars",
  "validation_policy": "strict",
  "plugin_allowlist": {
    "etlantic-polars": "==0.44.0"
  },
  "assets": {
    "rows": "json://data/sample.json",
    "out": "json://data/out.json"
  }
}
```

```bash
python -m etlantic validate pipeline.py:SamplePipeline \
  --profile profiles/prod.json --format sarif
python -m etlantic plan pipeline.py:SamplePipeline \
  --profile profiles/prod.json --format json
python -m etlantic run pipeline.py:SamplePipeline \
  --profile profiles/prod.json
```

Optional Airflow compile (install `etlantic-airflow`; does not install Airflow):

```bash
python -m pip install 'etlantic-airflow==0.44.0'
python -m etlantic compile pipeline.py:SamplePipeline \
  --profile profiles/prod.json --target airflow -o dags/
```

## Clone companion

```bash
git clone --branch v0.44.0 https://github.com/eddiethedean/etlantic.git
cd etlantic
uv sync --group dataframes
uv run python examples/sample_pilot/run_pilot.py
# or CLI from the sample directory:
cd examples/sample_pilot
uv run etlantic validate pipeline.py:PilotPipeline \
  --profile profiles/prod.json --format sarif
```

The companion registers only the selected Polars plugin on its planning
context, then validates, plans, and runs against the same runtime.

## Expected output

Plan fingerprints vary if the pipeline definition changes. A successful run
prints one explicit result for each gate:

```text
validation: passed
plan: plan:<fingerprint>
run: succeeded
```

The file sink at `examples/sample_pilot/data/out.json` contains:

```json
[
  {
    "id": 1,
    "name": "Ada"
  },
  {
    "id": 2,
    "name": "Grace"
  }
]
```

No secret values appear in validation, plan, or run output.

## Secrets

Keep resolved values out of profile JSON. See
[Secrets decision tree](../10_REFERENCE/SECRETS_DECISION.md).

## Related

- [Production profiles](../06_EXECUTION/PRODUCTION_PROFILES.md)
- [Ops examples](../01_GETTING_STARTED/OPS_EXAMPLES.md)
- [Capabilities CI starter](../01_GETTING_STARTED/CAPABILITIES.md#ci-starter)
