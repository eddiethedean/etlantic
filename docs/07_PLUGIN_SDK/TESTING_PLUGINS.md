# Testing Plugins

> **Status: Available in ETLantic 0.18.0** via `etlantic.testing`.

Testing helpers provide conformance suites so third-party plugins can prove
they implement the public protocols correctly.

## Shipped suites

| Suite | Module | Use for |
|---|---|---|
| Dataframe conformance | `etlantic.testing.run_conformance_suite` | Polars/Pandas-style plugins |
| SQL conformance | `etlantic.testing.run_sql_conformance_suite` | `SqlPlugin` |
| Orchestrator conformance | `etlantic.testing.run_orchestrator_conformance_suite` | `OrchestratorPlugin` |
| Secret conformance | `etlantic.testing.run_secret_conformance_suite` | `SecretProvider` |
| Write-semantics parity | `etlantic.testing.run_write_semantics_parity_suite` | Cross-engine write modes |
| Portable transform compiler | `etlantic.testing.run_portable_transform_conformance_suite` | `TransformCompiler` plugins |
| Tabular interchange smoke (Gate A) | `etlantic.testing.run_tabular_interchange_conformance_smoke` | Producer/consumer `PluginCapabilities` for `etlantic.interchange/1` |

Example:

```python
from etlantic.testing import run_conformance_suite

run_conformance_suite(my_plugin, engine="my-engine", sample_rows=rows)
```

```python
from etlantic.testing import run_portable_transform_conformance_suite
from my_engine import create_transform_compiler

run_portable_transform_conformance_suite(create_transform_compiler())
```

```python
from etlantic.testing import run_tabular_interchange_conformance_smoke

descriptor = run_tabular_interchange_conformance_smoke(producer_caps, consumer_caps)
assert descriptor.schema == "etlantic.interchange/1"
```

The portable suite is also importable as
`etlantic.testing.portable_transform_conformance`. It selects mandatory
fixtures from the exact profiles, actions, and functions a compiler
advertises. Claiming a capability without its fixture family fails the suite.

## Philosophy

Every plugin should be tested against the same expectations:

```text
Plugin
   │
   ▼
SDK Conformance Suite
   │
   ├── Discovery / registration
   ├── Capability advertisement
   ├── Semantic behavior
   └── Failure / diagnostic shape
```

A plugin that passes the matching suite should behave predictably with
ETLantic planning and runtime.

## Compatibility policy

- Claim only capabilities your compiler passes in the public suite.
- Pin `etlantic` (and this suite) to the minor you certified against (`==0.18.0`).
- Fail closed at `analyze()` for unsupported modes; do not degrade silently.
- Keep plans, explain payloads, and diagnostics secret-free.

## Next Step

See [Dataframe Plugin](DATAFRAME_PLUGIN.md), [SQL Plugin](SQL_PLUGIN.md),
[Orchestrator Plugin](ORCHESTRATOR_PLUGIN.md),
[Portable Transformation Compiler](PORTABLE_TRANSFORM_COMPILER.md), and
[Secret Provider](SECRET_PROVIDER.md) for protocol details.
