# Deployment

> **Status: Available in ETLantic 0.21.0.** This guide describes the bounded,
> single-tenant reference deployment. It is not a managed control plane.

## Process model

`PipelineRuntime` is application-owned and process-local. Its memory bindings,
plugin registry, scheduler registrations, and default report store are not
shared with another Python process. Create and configure a runtime in each
worker, and use durable backend storage for data or reports that must cross
process boundaries.

This reference model is suitable for one trusted application or worker per
runtime. ETLantic 0.18 does not coordinate a multi-worker runtime.

## Select and lock a profile

Deploy with an explicit Python or JSON `Profile`. A production profile must
have a non-empty `plugin_allowlist`; discovery fails closed when a selected
plugin is absent from the allowlist or does not match its version constraint.
Keep secret values in registered providers, not profiles, plans, or reports.

See [Production Profiles](PRODUCTION_PROFILES.md) for the complete checklist.

## Choose the orchestration path

- **Airflow compiles a plan.** Install `etlantic-airflow`, validate and plan,
  then run `etlantic compile TARGET --target airflow -o dags/`. Deploy the
  generated DAG through your normal Airflow release process.
- **Prefect executes directly.** Install `etlantic-prefect`, set
  `Profile(orchestrator="prefect")`, and call `Pipeline.run` or
  `Pipeline.arun`. The Prefect scheduler consumes the resolved plan; it does
  not re-plan the pipeline.

Both paths require backend plugins and durable artifact choices appropriate to
the target environment.

## CI gate

Validate before deployment and retain machine-readable evidence:

```bash
etlantic validate package.pipeline:CustomerPipeline --format json
etlantic validate package.pipeline:CustomerPipeline --format sarif
etlantic plan package.pipeline:CustomerPipeline --format json
```

Compile only after the plan is valid. Plans are deterministic, secret-free
coordination artifacts; they do not execute backend work.

## What adopters own

The adopter owns:

- worker/process topology, queues, retries, and durable artifact transport;
- tenant isolation, authorization, quotas, and noisy-neighbor controls;
- backend capacity testing, networking, credentials, and disaster recovery;
- image provenance, dependency locking, vulnerability response, and SBOM
  generation;
- observability retention and operational runbooks.

ETLantic 0.18 does not claim a multi-worker or multi-tenant control plane.

## Operational next steps

- [Ops Pilot](OPS_PILOT.md)
- [Production Readiness](PRODUCTION_READINESS.md)
- [Production Profiles](PRODUCTION_PROFILES.md)
