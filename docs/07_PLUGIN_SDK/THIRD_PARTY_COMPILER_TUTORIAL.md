# Third-Party Portable Compiler Tutorial

ETLantic 0.21.0 discovers portable transformation compilers through the
`etlantic.transform_compilers` entry-point group. A compiler analyzes,
compiles, and executes DTCS transformation plans under
`etlantic.transform-compiler/1`.

## 1. Create the package

```text
etlantic-acme/
├── pyproject.toml
└── src/
    └── etlantic_acme/
        ├── __init__.py
        └── compiler.py
```

Start with a core range matching the minor release you test:

```toml
[project]
name = "etlantic-acme"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["etlantic>=0.21.0,<0.22", "acme-frame>=2,<3"]

[project.entry-points."etlantic.transform_compilers"]
acme = "etlantic_acme:create_transform_compiler"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/etlantic_acme"]
```

Entry points execute Python in the host process. Production users must add the
compiler's discovered key or advertised name to `Profile.plugin_allowlist`.

## 2. Implement the protocol

Use the public transform compiler records. Begin with no claims, then add only
capabilities implemented with exact portable semantics.

```python
from collections.abc import Mapping, Sequence
from typing import Any

from etlantic.transform.compiler import (
    COMPILER_PROTOCOL,
    CompiledTransform,
    TransformCapabilities,
    TransformCompileContext,
    TransformCompilerInfo,
    TransformExecutionContext,
    TransformOutputBundle,
    TransformPlanningContext,
    TransformSupportReport,
)


class AcmeTransformCompiler:
    @property
    def info(self) -> TransformCompilerInfo:
        return TransformCompilerInfo(
            name="etlantic-acme",
            version="0.1.0",
            engine="acme",
            compiler_protocol=COMPILER_PROTOCOL,
            capabilities=TransformCapabilities(),
        )

    def analyze(
        self,
        definition: Mapping[str, Any],
        *,
        context: TransformPlanningContext,
        requirements: Mapping[str, Sequence[str]] | None = None,
    ) -> TransformSupportReport:
        # Compare every requested profile/action/function/mode with exact support.
        raise NotImplementedError

    def compile(
        self,
        definition: Mapping[str, Any],
        *,
        context: TransformCompileContext,
        requirements: Mapping[str, Sequence[str]] | None = None,
    ) -> CompiledTransform:
        # Produce a deterministic in-memory native plan; do not access data.
        raise NotImplementedError

    async def execute(
        self,
        compiled: CompiledTransform,
        *,
        inputs: Mapping[str, Any],
        parameters: Mapping[str, Any],
        context: TransformExecutionContext,
    ) -> TransformOutputBundle:
        # Execute only the already-analyzed and compiled artifact.
        raise NotImplementedError


def create_transform_compiler() -> AcmeTransformCompiler:
    return AcmeTransformCompiler()
```

`analyze()` and `compile()` are planning operations. They must not acquire
resources, read rows, resolve secrets, contact a backend, or import arbitrary
user modules. `CompiledTransform.native_plan` may hold an opaque backend object
in memory, but that object must never enter a serialized `PipelinePlan`.

## 3. Advertise exact claims

After implementing and testing the kernel profile, advertise its required
actions and functions:

```python
from etlantic.transform.compiler import TransformCapabilities
from etlantic.transform.protocol import KERNEL_PROFILE_V1

capabilities = TransformCapabilities(
    profiles=frozenset({KERNEL_PROFILE_V1}),
    actions=frozenset(
        {
            "dtcs:filter",
            "dtcs:project",
            "dtcs:with_fields",
            "dtcs:drop_fields",
            "dtcs:rename_fields",
        }
    ),
    functions=frozenset(
        {
            "dtcs:lower",
            "dtcs:substr",
            "dtcs:replace",
            "dtcs:coalesce",
        }
    ),
    lazy=True,
    eager=True,
)
```

Do not claim `portable-relational/1` until joins, unions, grouping,
aggregation, ordering, distinct/deduplication, and limits all satisfy the
profile. In 0.20.0, a relational claim must reject join collision policies
other than `fail`. If the backend is eager-only, set `lazy=False`.

Unsupported requirements must produce deterministic
`TransformSupportFinding` entries during analysis. Never silently approximate
semantics or fall back to raw SQL, Python/Pandas UDFs, or row collection.

## 4. Run the public conformance suite

```python
from etlantic.testing import run_portable_transform_conformance_suite
from etlantic_acme import create_transform_compiler


def test_portable_conformance() -> None:
    compiler = create_transform_compiler()
    run_portable_transform_conformance_suite(
        compiler,
        to_frame=make_acme_frame,
    )
```

`to_frame` converts fixture rows into the backend's input frame. ETLantic has
built-in factories only for its official engines, so third-party engines
normally provide this argument.

The suite selects mandatory fixtures from `compiler.info.capabilities` and
checks capability accuracy, deterministic compilation, scalar and relational
semantics, null behavior, joins, aggregation, output roles, ownership,
unsupported-operation diagnostics, bounded hostile IR, and redaction. A claim
without mandatory fixture coverage fails the suite.

Run the suite for every supported backend version and Python version. Add
backend differential tests where another conforming engine can serve as an
oracle.

## 5. Verify discovery

Install the wheel into an isolated environment with ETLantic 0.21.0, then:

```python
from etlantic.transform.discovery import discover_transform_compilers

compilers = discover_transform_compilers()
assert "acme" in compilers
print(compilers["acme"].info.to_dict())
```

See [Portable Transformation Compiler Protocol](PORTABLE_TRANSFORM_COMPILER.md),
[Portable Compiler Matrix](../10_REFERENCE/PORTABLE_COMPILER_MATRIX.md), and
[Testing Plugins](TESTING_PLUGINS.md).
# Third-Party Portable Compiler Tutorial

> **Status: Available in ETLantic 0.21.0.**

Build a transform compiler that claims DTCS profiles, registers through entry
points, and proves its claims with the public conformance suite.

## 1. Implement the protocol

```python
# my_compiler/plugin.py
from etlantic.transform.compiler import TransformCompiler

def create_transform_compiler() -> TransformCompiler:
    return MyCompiler()
```

Advertise only profiles and operations you actually lower. Fail closed in
`analyze()` for unclaimed modes (for example join `collisionPolicy` other
than `fail`).

## 2. Register the entry point

```toml
# pyproject.toml
[project.entry-points."etlantic.transform_compilers"]
myengine = "my_compiler.plugin:create_transform_compiler"
```

Depend on a matching ETLantic minor (`etlantic>=0.21.0,<0.22` for official
0.20 plugins).

## 3. Run the public conformance suite

```python
from etlantic.testing import run_portable_transform_conformance_suite
from my_compiler.plugin import create_transform_compiler

run_portable_transform_conformance_suite(create_transform_compiler())
```

Capability-selected fixtures become mandatory for every advertised
operation/function. Hypothesis property tests in ETLantic CI cover matching
and fingerprint stability for reference compilers—mirror that discipline.

## 4. Wire a profile

```python
from etlantic import Profile

Profile(
    name="pilot",
    dataframe_engine="myengine",
    portable_transform_policy="require",
    plugin_allowlist={"myengine": "==0.1.0"},
)
```

## Related

- [Portable Transform Compiler](PORTABLE_TRANSFORM_COMPILER.md)
- [Testing Plugins](TESTING_PLUGINS.md)
- [Portable compiler matrix](../10_REFERENCE/PORTABLE_COMPILER_MATRIX.md)
- [Capabilities](../01_GETTING_STARTED/CAPABILITIES.md)
