# What's New in ETLantic 0.46

> **Status: Available in ETLantic 0.46.0 (gate-ready Beta).** Streaming and
> dynamic control: bounded map/branch types, stream-time semantics, record-error
> policy, in-memory fixtures, and Experimental Kafka / schema-registry extras.

## Highlights

- **Bounded dynamic control** — explicit `map` / `reduce` / `conditional` /
  `failure` / `compensation` node kinds with deterministic child identity and
  hard expansion bounds (`PMDYN*`)
- **Stream-time model** — engine-free event-time, watermarks, triggers, and
  bounded vs unbounded semantics (`etlantic.streaming`); Spark types remain an
  optional projection
- **Change envelopes** — versioned metadata only (op, position, order, schema
  identity); **no event payloads** in plans, reports, or diagnostics
- **Record-error policy** — `fail` / `skip` / `quarantine` / `dead_letter` with
  offset-advance rules and identifier-only DLQ (`PMDLQ*`)
- **Schema-registry protocol** — `etlantic.schema-registry/1` identity and
  compatibility in core; production `Profile.schema_registry_allowlist` fail
  closed (`PMREG140`)
- **CLI** — `etlantic stream dead-letters inspect`, `redrive plan`, and
  `schemas check --store` (metadata only; never registers the candidate;
  payload keys exit `INVALID_MODEL`)
- **Experimental extras** — `etlantic-kafka` (`FakeKafka`) and
  `etlantic-schemaregistry` (`FakeConfluentRegistry`). Live brokers/registries
  are skipped unless opt-in env is set (`046-K-01`, `046-G-01`)
- **Optimizer** — unknown rewrite kinds fail closed (`PMOPT112`); no
  expansion/stream rewrite kinds in this line

## Adopter actions

| Who | Action |
|---|---|
| Everyone on **0.45.x** | Upgrade to `etlantic==0.46.0` with matching plugins; see [migration](../11_DEVELOPMENT/MIGRATION_0_45_TO_0_46.md) |
| Stream connector authors | Follow [Streaming connectors](../07_PLUGIN_SDK/STREAMING_CONNECTORS.md) |
| Registry adapter authors | Follow [Schema registry](../07_PLUGIN_SDK/SCHEMA_REGISTRY.md); pin `schema_registry_allowlist` in production |
| Operators | Keep production `plugin_allowlist` non-empty; Kafka/registry stay Experimental |

## Not in 0.46

- Live Kafka or live Confluent in required CI
- Kafka / Confluent SDK in core
- Optimizer expansion or stream-rewrite proof kinds
- Remote federation (0.47)
- AI-proposed optimizations (0.48)
- Medallion layers in core

## Related

- [Migration 0.45 → 0.46](../11_DEVELOPMENT/MIGRATION_0_45_TO_0_46.md)
- [Exit gate 0.46](../11_DEVELOPMENT/EXIT_GATE_0_46.md)
- [ADR-022](../11_DEVELOPMENT/adr/ADR-022-DYNAMIC-CONTROL-AND-STREAMING.md)
- [Capabilities](CAPABILITIES.md)
