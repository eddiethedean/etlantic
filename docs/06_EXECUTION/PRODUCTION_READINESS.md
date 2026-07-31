# Production Readiness and Deployment Boundaries

> **Status: Available in ETLantic 0.40.0.**

## Residual evaluation lead

| Topic | 0.40 |
|---|---|
| Maturity | **Beta** |
| Suitable for | Documented single-tenant pilot / reference topology |
| Support | Community; **no SLA** |
| Not included as GA | Production multi-tenant isolation; capacity SLA; compliance SoR |

ETLantic 0.40.0 is a **Beta** release suitable for the documented single-tenant
pilot deployment on this page. The milestone name “production readiness” (M6)
means the observability / run-history *pilot* slice—it does
**not** mean unrestricted enterprise production. **CP1** ships embeddable
identity, durable accept, and SSE via `ETLanticAPI` (plus thin
`create_reference_app` for non-CP demos) but is **not** multi-tenant GA
(graduation remains **0.43**). See the Beta envelope above
and CHANGELOG `[Unreleased]` for post-cut hardening that may land in a later
0.40.x patch without changing the documented pilot claims.

Experimental features remain experimental. Broader deployment topology,
multi-tenancy, and compliance attestations remain adopter-owned today. Supply
chain for v0.40.0 is expected at tag time as a SHA-256 artifact manifest and
GitHub provenance attestations; CycloneDX SBOM generation is optional (SBOM or
`sbom-warning.txt`)—see
[Release artifact verification](../01_GETTING_STARTED/RELEASE_ARTIFACT_VERIFICATION.md).
Multi-tenancy has a
[first-class gated plan](../11_DEVELOPMENT/MULTI_TENANT_CONTROL_PLANE_PLAN.md);
the other claims remain separate.

## Supported reference shape

```text
Version-pinned application process / container
  ├─ ETLantic core: model, validate, plan
  ├─ Explicitly allowlisted official plugins
  ├─ External secret provider at runtime
  ├─ External storage / engine
  └─ External orchestrator or supervised local process
```

Supported deployments are single-team or single-tenant, process-isolated, and
reproducible. Adopters own data-classification controls. ETLantic does not
provide production multi-tenant process isolation, a distributed scheduler,
or an SLA. Optional CP1 durable accept / event stores are incubation surfaces
(`etlantic.control_plane` / `etlantic-fastapi` `ETLanticAPI`) — **not** GA
isolation.

## Reference single-process topology

1. Pin `etlantic==0.40.0` and matching plugins in a lockfile.
2. Build an immutable image or venv; do not install untrusted entry points.
3. Configure `Profile.plugin_allowlist` for production.
4. Resolve secrets from env/files/keyring at runtime only.
5. Persist plans, reports, and compiled DAGs to application-owned storage.
6. Run `etlantic validate … --format sarif` in CI before deploy.
7. Health-check the process with your supervisor. **Core** ETLantic has no
   built-in HTTP health endpoint. Optional **CP1** FastAPI apps
   (`etlantic-fastapi` `create_app` / `ETLanticAPI`) expose `GET /health`
   (liveness) and `GET /ready` (readiness when stores are injected) — use those
   when you embed CP1; otherwise rely on the host supervisor.
8. On upgrade: pin forward, re-validate, re-plan, smoke-run one pipeline, keep
   the previous lockfile for rollback. Operator checklist:
   [Rollback and recovery](ROLLBACK_RECOVERY.md).

Airflow workers that execute compiled DAGs must install the same core/plugin
versions used at compile time, plus Airflow itself. Compilation does not ship
engine wheels to workers.

## Required controls

| Control | Requirement |
|---|---|
| Versions | Pin core and official plugins to the same tested release |
| Plugin trust | Set a non-empty `Profile.plugin_allowlist` in production |
| Install surface | Treat entry-point discovery as import-time execution; allowlists are selection controls |
| Secrets | Resolve at runtime; never embed values in plans or reports |
| Isolation | Use separate OS processes or containers for trust boundaries |
| Artifacts | Store plans, reports, and compiled DAGs under application controls |
| Validation | Run `etlantic validate` before plan, compile, or execution |
| Observability | Export logs/reports to an application-owned durable system |
| Recovery | Define engine-specific retries and idempotency outside assumptions |
| Retention | Define report/plan retention and filesystem ownership yourself |

## Boundaries on a general production claim

These remain outside the unrestricted enterprise envelope even when single-tenant
reference controls are shipped:

- Cross-tenant / multi-tenant isolation guarantees (beyond single-tenant keys)
- Formal denial-of-service capacity SLAs (partial I/O budgets only)
- Compliance-grade audit system of record (CLI reports are operational evidence)
- Multi-year LTS or compatibility support beyond the current published minor
- HA/DR, RPO/RTO, and compliance attestations (adopter-owned)
- Broader supply-chain programs beyond package allowlists, pins, SHA-256
  release digests, and GitHub attestations (CycloneDX SBOM is optional;
  confirm SBOM or `sbom-warning.txt` at tag time)

## Shipped / adopter-owned / residual (0.39)

| Concern | 0.40 status |
|---|---|
| Typed validate/plan/run | **Shipped** |
| Programmatic / JSON authoring (`PipelineDefinition`) | **Shipped** |
| Portable compilers (Polars/Pandas/SQL/PySpark) | **Shipped** |
| Plugin allowlists | **Shipped** (selection, not sandbox) |
| Safe I/O, outbound default-deny, serialization ban | **Shipped** |
| Artifact/cache isolation keys (single-tenant) | **Shipped** |
| Release SHA-256 digests + GitHub attestations | **Release-gated** (CycloneDX is optional; verify the published SBOM or `sbom-warning.txt`) |
| CP1 identity / durable accept / SSE (`ETLanticAPI`) | **Shipped (incubation)** — dual surface with thin `create_reference_app`; **≠ multi-tenant GA** |
| Durable multi-worker / multi-tenant control plane GA | **Planned** (0.40–0.42 → **0.43** graduation) |
| Cross-tenant isolation guarantees | **Planned first-class; adopter-owned until CP-GA** |
| Capacity / performance SLA | **Gap** — local baselines only |
| Compliance audit SoR | **Adopter-owned** |

## Deployment acceptance criteria

A deployment review should record supported versions, validation results, plan
fingerprints, plugin capability decisions, observed run reports, recovery
behavior, performance overhead, and every accepted security gap. Do not expand
beyond the bounded envelope if any required backend semantic is silently
degraded.

See [Evaluator Brief](../01_GETTING_STARTED/EVALUATOR.md),
[Ops Pilot](OPS_PILOT.md),
[Rollback and recovery](ROLLBACK_RECOVERY.md),
[Security](../02_FOUNDATIONS/SECURITY.md),
[Multi-Tenant Control Plane Plan](../11_DEVELOPMENT/MULTI_TENANT_CONTROL_PLANE_PLAN.md),
and [Support Policy](../11_DEVELOPMENT/SUPPORT.md).
