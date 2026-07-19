# Dataframe Plugin

A **Dataframe Plugin** implements the ETLantic Dataframe Plugin API for a
specific dataframe engine.

**Status: shipped in 0.5.0** (`etlantic.dataframe/1`).

Reference packages: `etlantic-polars`, `etlantic-pandas`.

!!! note "Companion compiler protocol (0.12)"
    The dataframe protocol still invokes native transformation callables.
    Portable compilation uses the separately versioned
    [portable transformation compiler](PORTABLE_TRANSFORM_COMPILER.md)
    (`etlantic.transform_compilers`). `etlantic-polars` ships both plugins.

## Responsibilities

- Materialize logical inputs into native frames
- Invoke registered `@Transformation.implementation(engine)` callables
- Validate outputs against contracts
- Inspect schemas into `NormalizedSchema`
- Enforce ownership / mutation isolation
- Collect lazy values only when the plan declares a boundary

Plugins are **not** responsible for pipeline planning, graph scheduling, or
contract generation.

## Minimal third-party plugin

### 1. Implement the protocol

```python
# my_engine_plugin/plugin.py
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from etlantic.capabilities import PluginCapabilities
from etlantic.dataframe import (
    DATAFRAME_PROTOCOL_VERSION,
    DataframeExecutionContext,
    DataframePluginInfo,
)


class MyEnginePlugin:
    def __init__(self) -> None:
        self._info = DataframePluginInfo(
            name="my-engine",
            engine="my-engine",
            version="0.1.0",
            protocol_version=DATAFRAME_PROTOCOL_VERSION,
            capabilities=PluginCapabilities(
                engine="my-engine",
                dataframe=True,
                eager=True,
                async_execution=False,
            ),
        )

    @property
    def info(self) -> DataframePluginInfo:
        return self._info

    def materialize_input(
        self,
        value: Any,
        *,
        contract_type: type[Any] | None,
        context: DataframeExecutionContext,
        port_name: str,
    ) -> Any:
        # Convert records / Arrow / native frames into your engine's type.
        return value

    def invoke(
        self,
        *,
        callable_: Any,
        inputs: Mapping[str, Any],
        parameters: Mapping[str, Any],
        context: DataframeExecutionContext,
    ) -> Any:
        kwargs = {**dict(parameters), **dict(inputs)}
        return callable_(**kwargs)

    # Implement remaining DataframePlugin methods: normalize_output,
    # validate_frame, inspect_schema, collect, clone_for_isolation, etc.
    # See etlantic.dataframe.DataframePlugin and packages/etlantic-polars.


def create_plugin() -> MyEnginePlugin:
    return MyEnginePlugin()
```

### 2. Register the entry point

In your package `pyproject.toml`:

```toml
[project.entry-points."etlantic.dataframe_plugins"]
my-engine = "my_engine_plugin.plugin:create_plugin"
```

### 3. Run conformance

```python
from etlantic.testing import run_conformance_suite
from my_engine_plugin.plugin import create_plugin

run_conformance_suite(
    create_plugin(),
    engine="my-engine",
    sample_rows=[{"id": 1, "name": "Ada"}],
)
```

### 4. Select it from a profile + allowlist

```python
from etlantic import Profile

profile = Profile(
    name="production",
    security_domain="production",
    dataframe_engine="my-engine",
    plugin_allowlist={"my-engine": ">=0.1,<1"},
)
```

Authors register implementations with the same engine name:

```python
@NormalizeCustomers.implementation("my-engine")
def normalize_my_engine(customers):
    ...
```

## Discovery

Plugins register via the `etlantic.dataframe_plugins` entry-point group.
`PipelineRuntime` discovers installed plugins at construction time. You can
also call `runtime.register_dataframe_plugin(engine, plugin)` or
`discover_dataframe_plugins()`.

## Conformance

Use `etlantic.testing.run_conformance_suite(plugin, engine=..., sample_rows=...)`
to exercise discovery, materialization, validation, schema inspection, and
ownership helpers. See [Testing Plugins](TESTING_PLUGINS.md).

## Gate A tabular interchange capabilities

> **Available in ETLantic 0.18.0.** Gate A covers **Polars ↔ Pandas** only.

Advertise supported mechanisms on `PluginCapabilities.interchange_mechanisms`
using the vocabulary in `etlantic.interchange.tabular.InterchangeMechanism`
(for example `arrow_c_data`, `records_fallback`). Planning selects a mechanism
via `select_mechanism` and records an `InterchangeDescriptor` under schema
`etlantic.interchange/1`.

Do **not** treat best-effort Arrow conversion helpers as Gate A evidence.
Prove capability honesty with
`etlantic.testing.run_tabular_interchange_conformance_smoke(producer_caps, consumer_caps)`.

See [API — Plan and Runtime](../10_REFERENCE/API_PLAN_RUNTIME.md#gate-a-tabular-interchange-etlanticinterchange1)
and [Interchange Gate A FAQ](../01_GETTING_STARTED/INTERCHANGE_GATE_A_FAQ.md).

## See also

- Shipped references: `packages/etlantic-polars`, `packages/etlantic-pandas`
- [Dataframe Plugins (execution)](../06_EXECUTION/DATAFRAME_PLUGINS.md)
- Runnable parity example (checkout): `examples/dataframe_parity.py`
- Gate A example (checkout): `examples/interchange_polars_pandas.py`
