# Diagnostic-code stability tiers (0.37)

> **Status: Available in ETLantic 0.41.0.** Foundation freeze inventory for
> diagnostic **code families** (alphabetic prefix before the numeric suffix).
> Machine-readable companion:
> [`diagnostic-stability-tiers.json`](https://github.com/eddiethedean/etlantic/blob/main/src/etlantic/schemas/diagnostic-stability-tiers.json)
> (packaged under `etlantic.schemas`).

These tiers freeze **identity and compatibility expectations** for code
families—not every message string. New codes may be added within a family;
incompatible renumbering or removal of a **stable** family requires migration
notes. Exhaustive code→source index:
[Diagnostics catalog](DIAGNOSTICS_CATALOG.md). Human meanings:
[Diagnostics](DIAGNOSTICS.md).

## Tier meanings

| Tier | Meaning |
|---|---|
| `stable` | Part of the 0.39 foundation envelope. Existing codes keep identity; incompatible renumbering or removal needs migration notes. |
| `provisional` | Public and emitted today, but the family may change before a later explicit graduation (aligned with provisional wire surfaces such as `etlantic.quality/1`). |
| `experimental` | May change or be removed without a 0.40 Beta compatibility obligation. |

## Family tiers

| Family | Tier | Notes |
|---|---|---|
| `PMAUTH` | stable | Authoring lifecycle / resolve |
| `PMCAT` | stable | Authoring catalog policy |
| `PMCFG` | stable | Configuration and profiles |
| `PMCONN` | stable | Connector protocols, bindings, landing zone, publication |
| `PMDATA` | stable | Data-contract integration |
| `PMDF` | stable | Dataframe plugin diagnostics |
| `PMEXEC` | stable | Execution lifecycle |
| `PMGEN` | stable | Contract / documentation generation |
| `PMORCH` | stable | Orchestration / compile |
| `PMPIPE` | stable | Pipeline topology and wiring |
| `PMPLAN` | stable | Planning and capability resolution |
| `PMPLUG` | stable | Plugin trust / allowlist / compatibility |
| `PMQTY` | provisional | Portable quality (`etlantic.quality/1` still provisional) |
| `PMSCHED` | stable | Scheduler / local run selection |
| `PMSEC` | stable | Security policy (I/O, serialization, outbound) |
| `PMSPARK` | stable | Spark capability and runtime |
| `PMSQL` | stable | SQL capability and runtime |
| `PMSRC` | stable | Source / Safe I/O loading |
| `PMTRN` | stable | Transformation definitions |
| `PMXFORM` | stable | Portable transformation IR / compilers |

Standards namespaces (`ODCS`, `DTCS`, `DPCS`) keep their upstream identity when
emitted. Declare a tier in the JSON inventory before shipping a **new**
ETLantic-owned family.

## Drift check

```bash
uv run python scripts/check_diagnostic_stability.py
```

Every shipped code family under `src/etlantic` must appear in
`diagnostic-stability-tiers.json`.

## See also

- [Diagnostics catalog](DIAGNOSTICS_CATALOG.md)
- [Diagnostics](DIAGNOSTICS.md)
- [Surface inventory](SURFACE_INVENTORY.md)
- [Capabilities](../01_GETTING_STARTED/CAPABILITIES.md#supported-standards-policy-040)
