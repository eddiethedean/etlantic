# Ops Pilot Guide

> **Status: Available in ETLantic 0.14.0.** Alpha operational checklist—not a
> multi-tenant deployment product.

Use this page for a **bounded pilot**: one team, pinned packages, process
isolation, and fail-closed production profiles. It does not claim SLA, HA, or
compliance certification.

## Pin matrix

```bash
pip install 'etlantic==0.14.0'
# Only the engines you need:
pip install 'etlantic-polars==0.14.0'   # or pandas / sql / pyspark / airflow
```

Record the exact versions in your lockfile. Production profiles should pin
plugins via `Profile.plugin_allowlist` (bare versions are accepted as
`==version`).

## Required controls

1. **Non-empty `plugin_allowlist`** on production / `security_domain=production`
2. **No secrets** in plans, reports, CI logs, or schema history
3. **Process isolation** — do not multi-tenant in one process
4. **SARIF validate** in CI before compile/generate

```bash
etlantic validate path/to/pipeline.py:MyPipeline \
  --profile production --format sarif
etlantic plan path/to/pipeline.py:MyPipeline \
  --profile production --format json
```

## Runtime configuration

- Profiles: [Profiles](../05_PIPELINES/PROFILES.md)
- Env / Profile knobs: [Runtime configuration](../10_REFERENCE/RUNTIME_CONFIGURATION.md)
- Secrets: env or mounted file providers; optional `etlantic-keyring`

## Reports and observability

- Run reports are **process-local operational evidence**, not an audit system
  of record. Export with `etlantic report` or a file report store when you need
  persistence.
- Optional OpenTelemetry adapter: `pip install 'etlantic[otel]'` — see
  [Capabilities](../01_GETTING_STARTED/CAPABILITIES.md).

## Airflow handoff

1. Plan with a production profile and allowlist that includes your orchestrator
2. `etlantic compile TARGET --target airflow -o dags/ --profile production`
3. Deploy the generated DAG with your normal Airflow process

Ownership: ETLantic owns modeling, validation, and the secret-free plan;
Airflow owns scheduling and worker execution; engines own dataframe/SQL/Spark
compute.

## Failure ownership

| Symptom | Likely owner |
|---|---|
| Validation / `PMPLUG*` / wiring diagnostics | ETLantic model / profile |
| Engine OOM, SQL errors, Spark job failure | Engine / plugin / infrastructure |
| DAG not scheduled | Airflow / ops |
| Secret resolution failure | Secret provider / mount / env |

## Related

- [Production Readiness](PRODUCTION_READINESS.md)
- [Evaluator Brief](../01_GETTING_STARTED/EVALUATOR.md)
- [Security](../02_FOUNDATIONS/SECURITY.md)
- [Support](../11_DEVELOPMENT/SUPPORT.md)
