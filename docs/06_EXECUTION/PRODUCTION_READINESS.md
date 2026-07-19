# Production Readiness and Deployment Boundaries

ETLantic 0.14.0 is alpha. Use this page to scope a controlled evaluation; it is
not a production-readiness claim.

## Supported pilot shape

```text
Version-pinned application process / container
  ├─ ETLantic core: model, validate, plan
  ├─ Explicitly allowlisted official plugins
  ├─ External secret provider at runtime
  ├─ External storage / engine
  └─ External orchestrator or supervised local process
```

Suitable pilots are single-team, process-isolated, reproducible, and use
non-sensitive or synthetic data. ETLantic does not provide multi-tenant process
isolation, a distributed scheduler, durable control-plane state, or an SLA.

## Reference single-process topology

1. Pin `etlantic==0.14.0` and matching plugins in a lockfile.
2. Build an immutable image or venv; do not install untrusted entry points.
3. Configure `Profile.plugin_allowlist` for production.
4. Resolve secrets from env/files/keyring at runtime only.
5. Persist plans, reports, and compiled DAGs to application-owned storage.
6. Run `etlantic validate … --format sarif` in CI before deploy.
7. Health-check the process with your supervisor (ETLantic has no built-in HTTP
   health endpoint).
8. On upgrade: pin forward, re-validate, re-plan, smoke-run one pipeline, keep
   the previous lockfile for rollback.

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

## Explicit blockers for a general production claim

- Supply-chain provenance beyond package allowlists and version pins
- Cross-run and cross-tenant artifact/cache isolation guarantees
- Outbound destination constraints
- Planning and loading denial-of-service budgets
- Formal unsafe-serialization prohibition across all plugins
- Stable 1.0 compatibility and support windows
- HA/DR, RPO/RTO, and compliance attestations (adopter-owned)

## Shipped / adopter-owned / gap

| Concern | 0.14 status |
|---|---|
| Typed validate/plan/run | Shipped |
| Polars kernel portable compile | Shipped |
| Plugin allowlists | Shipped (selection, not sandbox) |
| Durable multi-worker control plane | Gap |
| Signed SBOM / provenance | Gap |
| Capacity / performance SLA | Gap — see benchmarks docs for local baselines only |

## Pilot exit criteria

An evaluation should record supported versions, validation results, plan
fingerprints, plugin capability decisions, observed run reports, recovery
behavior, performance overhead, and every accepted security gap. Do not expand
the pilot if any required backend semantic is silently degraded.

See [Evaluator Brief](../01_GETTING_STARTED/EVALUATOR.md),
[Ops Pilot](OPS_PILOT.md),
[Security](../02_FOUNDATIONS/SECURITY.md), and
[Support Policy](../11_DEVELOPMENT/SUPPORT.md).
