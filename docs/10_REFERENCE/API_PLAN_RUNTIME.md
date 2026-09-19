# API — Plan and Runtime

> **Status: Available in ETLantic 0.54.0 (published Beta).**

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

> **ETLantic 0.54.0 (published Beta).** Versioned, capability-driven tabular
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

## Experimental adaptive physical execution (0.53)

Local `/2` execution requires a packaged fixture-qualified support row and a
fresh whole-DAG admission. Stored portable definitions, contract fingerprints,
compiler/dataframe versions, bindings and exact executor evidence are checked
before resources or I/O. Selected adapters are pinned for the invocation;
changing a runtime registry after admission cannot redirect execution.

Adaptive `RunRequest.implementation_overrides` values are placement target IDs.
When opted-in planning independently produces an explicit `/1` fallback,
`LocalScheduler` executes its resolved engine descriptors; the original target
IDs are not reinterpreted as engine names. Ordinary explicit requests retain
their existing engine override precedence. Stored `/2` plans cannot downgrade
to explicit execution.

Boundary requirements use closed versioned metadata maps. Bare truthy flags
and unknown fields or versions reject before effects:

| Graph metadata | Required descriptor / behavior |
|---|---|
| `etlantic.collection_required` on a consumer | `{"schema":"etlantic.physical_operation/1","kind":"collection","max_rows":1000,"max_bytes":1048576}`; executes an explicit edge collection and enforces both finite positive integer bounds. |
| `etlantic.validation_required` | `{"schema":"etlantic.physical_operation/1","kind":"validation","port":"result","outcome":"fail"}`; invokes output contract validation on the contracted port. Outcomes also support reject, quarantine, warn and observe_only through the existing validation protocol. |
| `etlantic.materialization_required` | `{"schema":"etlantic.physical_operation/1","kind":"materialization","checkpoint":"checkpoint_name"}`; atomically stores records and integrity/contract/security metadata in a named local workspace checkpoint. |
| `etlantic.reuse_artifact` | `{"schema":"etlantic.physical_operation/1","kind":"reuse","checkpoint":"checkpoint_name"}`; retains its producer dependency, verifies the checkpoint and selects it or the producer on a miss/stale record. Integrity or authorization failures fail the boundary. |

For materialization/reuse, `checkpoint` defaults to `memory`; names contain only
ASCII letters, digits, `_` and `-`. Named checkpoints require `workspace` during
scheduler admission. An optional `ttl_seconds` must be finite and positive.
`port` defaults to the first contracted output and must name a declared port.
Collection bounds do not change existing explicit `/1` collection behavior.

Physical publication retains a committed receipt before logical sink success.
Qualified JSON/CSV overwrite uses safe atomic, destination-locked writes;
missing acknowledgements retain `PMADP524` reconciliation identities and forbid
blind retry. Cancellation drains owned cleanup under a shield and its configured
abandonment deadline; unresolved owners remain in `PMADP523` obligations.
Protocol metadata excludes native serializers, row payloads and free-form backend
exception text. Physical counters are nested under namespaced report metadata.

The qualification campaign and exact backend versions are documented in
[0.53 evidence](../11_DEVELOPMENT/evidence/adaptive_0_53/README.md). These APIs
remain Experimental and require Sol review; a passing implementation-side
campaign is not independent release approval.
