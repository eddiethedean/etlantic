# Exit Gate 0.34 — Operations, Evidence, and Production Readiness (M6)

> **Status: Shipped in ETLantic 0.34.0.** Medallantic M6 operations and
> production-readiness surfaces ship in **0.34.0**.

| Deliverable | Status |
|---|---|
| Lifecycle event correlation (`etlantic.lifecycle_event/1`) | Done |
| Observability provider protocol (`etlantic.observability/1`) | Done |
| Run history provider protocol + file/memory reference providers | Done |
| Event consumer protocol + trend reference consumer | Done |
| Runtime observability bridge wired to EventBus / RunLogger | Done |
| Profile composition (`observability_*`, `run_history_provider`) | Done |
| Plugin entry-point groups for observability/history/consumers | Done |
| Conformance suites (observability, run history, event consumer) | Done |
| Production conformance runner | Done |
| Medallantic `explain_medallion_plan` + lifecycle views | Done |
| Medallantic dev/test/prod profile templates | Done |
| CLI `etlantic report query` + history workspace wiring | Done |
| Docs: What's New / Migration 0.33→0.34 / this exit gate | Done |
| Core + plugins + medallantic bumped to 0.34.0 | Done |

## Engine bar

- Observability and run history remain **optional providers** — core stays
  storage-agnostic.
- Production profiles still require explicit `plugin_allowlist` and assets.
- `durable_audit` delivery fails closed when required provider flush/history
  persistence fails.

## Acceptance checklist

- [x] Observability / run-history / event-consumer conformance green
- [x] Production conformance checks for profile allowlist
- [x] Medallantic operations tests (`test_operations_0_34.py`) green
- [x] Lifecycle events carry plan/region/backend correlation fields
- [x] No wire-schema reset for `pipeline/1` or `plan/1`

## Residual / follow-ons (0.35+)

- Automated SparkForge project inventory (**M7 / 0.35**)
- First-party SQL/Delta run-history PyPI plugins (extension pattern documented)
- Multi-tenant control plane (**0.39+**)

## See also

- [ROADMAP § 0.34](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md#034--operations-evidence-and-production-readiness)
- [What's New 0.34](../01_GETTING_STARTED/WHATS_NEW_0_34.md)
- [Migration 0.33 → 0.34](MIGRATION_0_33_TO_0_34.md)
- [Exit gate 0.33](EXIT_GATE_0_33.md)
- [Medallantic roadmap](https://github.com/eddiethedean/etlantic/blob/main/packages/medallantic/ROADMAP.md)
