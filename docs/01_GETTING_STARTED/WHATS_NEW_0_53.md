# What's new in 0.53

> **Status: Available in ETLantic 0.53.0 (Beta release candidate); adaptive execution is Experimental.**

ETLantic 0.53.0 is a Beta release candidate. Local adaptive physical-DAG
execution is **Experimental**, with packaged fixture-qualified support for
Local, Polars, Pandas and both single-cut Polars/Pandas directions.

Explicit `/1` execution remains the default. Adaptive planning captures the
effective request before validation and placement. Local execution verifies
the stored scope, contracts, bindings and exact dependencies before any I/O,
then schedules the stored physical DAG with pinned adapters.

Transfers, finite collection, validation, local checkpoints/reuse and
publication are explicit units. Logical reports retain outcomes and provenance;
deadlines fence late results, cleanup retains ownership obligations, and unknown
commit outcomes retain reconciliation receipts without blind retry.

Install core and first-party plugins together on the 0.53.0 line after release.
See [Migration 0.52 → 0.53](../11_DEVELOPMENT/MIGRATION_0_52_TO_0_53.md),
[the API contract](../10_REFERENCE/API_PLAN_RUNTIME.md),
[qualification evidence](../11_DEVELOPMENT/evidence/adaptive_0_53/README.md),
and [the exit gate](../11_DEVELOPMENT/EXIT_GATE_0_53.md).

The seven-engine portable baseline remains an explicit-execution capability.
Adaptive SQL, DuckDB, Spark, DataFusion, durable/remote/dynamic execution,
native bodies and arbitrary topologies are excluded. Phase 0.54 owns broader
qualification and availability; installation alone grants no adaptive authority.
