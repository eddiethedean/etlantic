# What's New in ETLantic 0.52

> **Status: Available in ETLantic 0.52.0 (published Beta).**

ETLantic 0.52.0 adds deterministic adaptive planning for opt-in profiles. The
planner emits the closed `etlantic.plan/2` document with a complete candidate
matrix, canonical objective, bounded explain output, and a seven-kind physical
DAG. Planning remains side-effect free; adaptive runtime execution and external
compilation reject the document before I/O.

Existing explicit profiles continue to produce canonical `etlantic.plan/1`
documents. Native transformation implementations remain explicit `/1` escape
hatches and are never adaptive candidates.

See [Migration 0.51 → 0.52](../11_DEVELOPMENT/MIGRATION_0_51_TO_0_52.md) and the
[0.52 exit gate](../11_DEVELOPMENT/EXIT_GATE_0_52.md).
