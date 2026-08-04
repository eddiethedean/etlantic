# Deployment

> **Status: Available in ETLantic 0.42.0.** This guide describes the bounded,
> single-tenant reference deployment. It is not the
> [planned multi-tenant control plane](../11_DEVELOPMENT/MULTI_TENANT_CONTROL_PLANE_PLAN.md).

## Residual evaluation lead

| Topic | 0.42 |
|---|---|
| Maturity | Beta (PyPI) |
| Topology | Single trusted process / worker per runtime (reference) |
| Multi-worker / multi-tenant control plane | CP4 policy/audit RC incubation; **not** production multi-tenant (**0.43**) |
| SLA | None (community support) |

## Process model

`PipelineRuntime` is application-owned and process-local. Its memory bindings,
plugin registry, scheduler registrations, and default report store are not
shared with another Python process. Create and configure a runtime in each
worker, and use durable backend storage for data or reports that must cross
process boundaries.

This reference model is suitable for one trusted application or worker per
runtime. ETLantic 0.42 does not replace adopter-owned brokers or worker
supervisors; optional CP3/CP4 control-plane stores coordinate accepted work across hosts.

## Reference topologies

### A. Single process (local / container)

1. Pin `etlantic==0.42.0` and matching plugins in a lockfile.
2. Mount or bake `profiles/production.json` with `security_mode="production"`
   and a non-empty `plugin_allowlist`.
3. Resolve secrets from env / files / keyring at runtime only.
4. Persist `.etlantic/` reports (or an application-owned store) on a durable volume.
5. Health-check the process with your supervisor (no built-in HTTP probe).

Checklist: [Production Profiles](PRODUCTION_PROFILES.md),
[Ops Pilot](OPS_PILOT.md).

### B. Airflow workers (compile-only path)

1. CI: `validate` → `plan` → `etlantic compile … --target airflow -o dags/`.
2. Deploy DAG artifacts through your normal Airflow release process.
3. Workers that execute compiled DAGs must install the **same** core/plugin
   minors used at compile time, plus Apache Airflow itself.
4. `etlantic-airflow` does **not** install Airflow and does not run the
   pipeline inside the compiler process.

Checklist: [Airflow tutorial](AIRFLOW_TUTORIAL.md),
[Compilation](COMPILATION.md).

### C. Prefect local MVP

1. Install `etlantic-prefect==0.42.0`.
2. Set `Profile(orchestrator="prefect")` and call `Pipeline.run` / `arun`.
3. Prefect consumes the resolved plan (direct execution). Deployment/serve
   flows remain future—do not assume them from this package.

Checklist: [Prefect example](../09_EXAMPLES/PREFECT_RUN.md).

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
python -m etlantic validate package.pipeline:CustomerPipeline --format json
python -m etlantic validate package.pipeline:CustomerPipeline --format sarif
python -m etlantic plan package.pipeline:CustomerPipeline --format json
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

ETLantic 0.42 does not claim a production multi-tenant control plane. CP4
incubates durable submission, leases, fencing, and preview workspaces, but the
production multi-tenant claim remains gated to **0.43**. None of those future
guarantees may be assumed for the reference topology on this page.

## Operational next steps

- [Ops Pilot](OPS_PILOT.md)
- [Rollback and recovery](ROLLBACK_RECOVERY.md)
- [Production Readiness](PRODUCTION_READINESS.md)
- [Production Profiles](PRODUCTION_PROFILES.md)
- [Performance envelope](../01_GETTING_STARTED/PERFORMANCE_ENVELOPE.md)
- [Multi-Tenant Control Plane Plan](../11_DEVELOPMENT/MULTI_TENANT_CONTROL_PLANE_PLAN.md)
