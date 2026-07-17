# Production Readiness and Deployment Boundaries

ETLantic 0.11 is alpha. Use this page to scope a controlled evaluation; it is
not a production-readiness claim.

## Supported pilot shape

```text
Version-pinned application process
  ├─ ETLantic core: model, validate, plan
  ├─ Explicitly allowlisted official plugins
  ├─ External secret provider at runtime
  ├─ External storage / engine
  └─ External orchestrator or supervised local process
```

Suitable pilots are single-team, process-isolated, reproducible, and use
non-sensitive or synthetic data. ETLantic does not provide multi-tenant process
isolation, a distributed scheduler, durable control-plane state, or an SLA.

## Required controls

| Control | Requirement |
|---|---|
| Versions | Pin core and official plugins to the same tested release |
| Plugin trust | Set a non-empty `Profile.plugin_allowlist` in production |
| Secrets | Resolve at runtime; never embed values in plans or reports |
| Isolation | Use separate OS processes or containers for trust boundaries |
| Artifacts | Store plans, reports, and compiled DAGs under application controls |
| Validation | Run `etlantic validate` before plan, compile, or execution |
| Observability | Export logs/reports to an application-owned durable system |
| Recovery | Define engine-specific retries and idempotency outside assumptions |

## Explicit blockers for a general production claim

- Supply-chain provenance beyond package allowlists and version pins
- Cross-run and cross-tenant artifact/cache isolation guarantees
- Outbound destination constraints
- Planning and loading denial-of-service budgets
- Formal unsafe-serialization prohibition across all plugins
- Stable 1.0 compatibility and support windows

## Pilot exit criteria

An evaluation should record supported versions, validation results, plan
fingerprints, plugin capability decisions, observed run reports, recovery
behavior, performance overhead, and every accepted security gap. Do not expand
the pilot if any required backend semantic is silently degraded.

See [Evaluator Brief](../01_GETTING_STARTED/EVALUATOR.md),
[Security](../02_FOUNDATIONS/SECURITY.md), and
[Support Policy](../11_DEVELOPMENT/SUPPORT.md).
