# API — Plan and Runtime

> Generated from package source. Hub: [Python API Reference](API_REFERENCE.md).

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

ODCS / DTCS / DPCS loading, diffs, and bundle helpers:

::: etlantic.interchange
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]

## Gate A tabular interchange (`etlantic.interchange/1`)

> **Available in ETLantic 0.18.0.** Versioned, capability-driven tabular
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

