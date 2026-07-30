# API — Plan and Runtime

> **Status: Available in ETLantic 0.35.0.**

> Generated from package source. Hub: [Python API Reference](API_REFERENCE.md).

## 0.21 trust and plan essentials

| API | Behavior |
|---|---|
| `Profile.security_mode` | `development` \| `test` \| `production`; production fail-closed trust uses **mode only** |
| `Profile.plugin_allowlist` | Required in production; authorize **before** `entry_point.load()` (selection, not sandbox; install is the trust boundary) |
| `Profile.safe_io` / `Profile.outbound` | Safe filesystem writes and outbound HTTP policy (0.20) |
| `resolve_profile(name, allow_adhoc_profile=False)` | Unknown bare names raise `PMCFG100` unless ad hoc is allowed |
| `Profile.from_dict(..., accept_legacy_bindings=False)` | Legacy `bindings`-only JSON fails closed with `PMCFG111`; pass `True` / `--accept-legacy-bindings` to allow |
| `PipelinePlan.from_dict` / `plan_from_json` | Require wire `schema: "etlantic.plan/1"`; verify fingerprint by default |
| `verify_plan_fingerprint(plan)` | Public check; also called before `compile_plan` and local run |
| `deep_freeze(value)` | Freeze nested mappings→`MappingProxyType`, lists→tuples, sets→frozensets; dataclasses/unknown objects unchanged |

See [Migration 0.20 → 0.21](../11_DEVELOPMENT/MIGRATION_0_20_TO_0_21.md) and
[What's new in 0.21](../01_GETTING_STARTED/WHATS_NEW_0_21.md).

## Validation and diagnostics

::: etlantic.diagnostics
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

::: etlantic.validation
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

::: etlantic.policy
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

## Profiles, planning, and registries

::: etlantic.profile
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

::: etlantic.plan
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

::: etlantic.registry
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

::: etlantic.plugin_trust
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

::: etlantic.model
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

## Local runtime and reports

::: etlantic.runtime
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

::: etlantic.lifecycle
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

::: etlantic.reports
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

## Storage and secrets

::: etlantic.storage
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

::: etlantic.secrets
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

## Contract interchange

[ODCS](../03_DATA_CONTRACTS/ODCS.md) / [DTCS](../04_TRANSFORMATIONS/DTCS.md) / [DPCS](../05_PIPELINES/DPCS.md) loading, diffs, and bundle helpers:

::: etlantic.interchange
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

## Gate A tabular interchange (`etlantic.interchange/1`)

> **Available in ETLantic 0.35.0.** Versioned, capability-driven tabular
> interchange for **Polars ↔ Pandas** boundaries. PySpark/SQL Gate A pairs are
> not in scope yet. Legacy Arrow-assisted helpers (when PyArrow is installed)
> are **not** the Gate A contract.

Planner and runtime use descriptors, mechanism selection, fidelity checks, and
evidence types from `etlantic.interchange.tabular`. Adopter guides:
[Interchange Gate A FAQ](../01_GETTING_STARTED/INTERCHANGE_GATE_A_FAQ.md),
[Polars ↔ Pandas example](../09_EXAMPLES/INTERCHANGE_POLARS_PANDAS.md).

::: etlantic.interchange.tabular
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]
