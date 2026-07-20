# Building an ETLantic Plugin

This is the canonical guide for creating and maintaining an independently
distributed ETLantic plugin. Reference plugins in the ETLantic repository and
third-party plugins should follow the same package, discovery, capability,
security, testing, and release rules described here.

The examples use a dataframe engine named `acme`. Replace `acme` with a short,
stable engine identifier and then follow the protocol page for your plugin
category.

## What counts as a plugin

An ETLantic plugin implements one of the public extension protocols and, when
the extension is discoverable, exposes a factory through a Python entry point.
A plugin may provide more than one related extension, such as a dataframe
runtime and a portable transformation compiler.

Libraries that only convert models or provide authoring helpers may integrate
with ETLantic without being discoverable plugins. Do not invent an entry-point
group for them.

ETLantic core owns logical pipeline meaning, validation, planning, and result
normalization. A plugin realizes that meaning for a backend; it must not change
contracts, silently weaken requested behavior, or introduce backend-specific
concepts into the core model.

## 1. Choose one public extension point

Start with the narrowest protocol that owns the behavior:

| Extension | Public API | Entry-point group | Conformance suite |
|---|---|---|---|
| Dataframe runtime | `etlantic.dataframe` | `etlantic.dataframe_plugins` | `run_conformance_suite` |
| SQL runtime | `etlantic.sql` | `etlantic.sql_plugins` | `run_sql_conformance_suite` |
| Spark runtime | `etlantic.spark` | `etlantic.spark_plugins` | Backend tests; see [PySpark Plugin](PYSPARK_PLUGIN.md) |
| Spark session/provider | `etlantic.spark` | `etlantic.spark_providers` | Provider lifecycle tests |
| Orchestrator compiler | `etlantic.orchestration` | `etlantic.orchestrator_plugins` | `run_orchestrator_conformance_suite` |
| Portable transform compiler | `etlantic.transform` | `etlantic.transform_compilers` | `run_portable_transform_conformance_suite` |
| Secret provider | `etlantic.secrets` | Runtime/profile registration | `run_secret_conformance_suite` |

Storage, resource, and observability extension documents describe integration
patterns that are not all backed by package entry-point discovery in 0.15. Do
not publish against a proposed discovery group. Use the public runtime/profile
registration surface documented for that category.

Read the relevant protocol page before implementing the package:

- [Dataframe Plugin](DATAFRAME_PLUGIN.md)
- [SQL Plugin](SQL_PLUGIN.md)
- [PySpark Plugin](PYSPARK_PLUGIN.md)
- [Spark Provider](SPARK_PROVIDER.md)
- [Orchestrator Plugin](ORCHESTRATOR_PLUGIN.md)
- [Portable Transformation Compiler](PORTABLE_TRANSFORM_COMPILER.md)
- [Secret Provider](SECRET_PROVIDER.md)

## 2. Create the package

Use a standard `src`-layout Python package. The distribution name should
normally be `etlantic-<engine>` and the import package `etlantic_<engine>`.
Community publishers may add an organization qualifier when the short name is
ambiguous.

```text
etlantic-acme/
├── pyproject.toml
├── README.md
├── LICENSE
├── CHANGELOG.md
├── src/
│   └── etlantic_acme/
│       ├── __init__.py
│       ├── plugin.py
│       └── py.typed
└── tests/
    ├── test_conformance.py
    ├── test_discovery.py
    └── test_security.py
```

The `py.typed` marker is required for a typed distribution. Keep backend
dependencies in this package rather than adding them to ETLantic core.

A minimal `pyproject.toml` is:

```toml
[project]
name = "etlantic-acme"
version = "0.1.0"
description = "Acme dataframe execution plugin for ETLantic."
readme = "README.md"
license = "MIT"
requires-python = ">=3.11"
dependencies = [
    "etlantic>=0.21.0,<0.22",
    "acme-dataframe>=2,<3",
]
classifiers = [
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3 :: Only",
    "Typing :: Typed",
]

[project.entry-points."etlantic.dataframe_plugins"]
acme = "etlantic_acme:create_plugin"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/etlantic_acme"]
```

Use a bounded ETLantic minor range that you actually test. Do not claim
compatibility with future minors. Backend libraries may be optional extras when
the base package has useful behavior without them.

## 3. Implement only public protocols

Import protocol types from the documented public modules. Never import private
underscore modules or reach into another plugin's implementation.

For a dataframe plugin, the public shape begins like this:

```python
from __future__ import annotations

from etlantic.capabilities import PluginCapabilities
from etlantic.dataframe import (
    DATAFRAME_PROTOCOL_VERSION,
    DataframePluginInfo,
)

__version__ = "0.1.0"


class AcmeDataframePlugin:
    def __init__(self) -> None:
        self._info = DataframePluginInfo(
            name="etlantic-acme",
            engine="acme",
            version=__version__,
            protocol_version=DATAFRAME_PROTOCOL_VERSION,
            capabilities=PluginCapabilities(
                engine="acme",
                dataframe=True,
                eager=True,
                lazy=False,
                schema_inspection=True,
            ),
        )

    @property
    def info(self) -> DataframePluginInfo:
        return self._info

    # Implement every method required by etlantic.dataframe.DataframePlugin.


def create_plugin() -> AcmeDataframePlugin:
    return AcmeDataframePlugin()
```

Export the factory from `etlantic_acme/__init__.py`:

```python
from etlantic_acme.plugin import AcmeDataframePlugin, create_plugin

__all__ = ["AcmeDataframePlugin", "create_plugin"]
```

The entry point must resolve to a zero-argument factory. Importing the module or
calling the factory must not connect to a database, start a cluster, read user
data, or resolve credentials. Acquire live resources only through the runtime
lifecycle defined by the protocol.

## 4. Declare capabilities truthfully

Capabilities are executable compatibility claims, not marketing metadata.
Declare a capability only when:

1. the behavior is implemented without changing pipeline semantics;
2. unsupported inputs fail before mutation;
3. the matching conformance and backend tests pass; and
4. limitations are documented.

Do not silently collect a lazy dataset, fall back to another engine, weaken a
write mode, ignore cancellation, or emulate a transaction unless the public
protocol explicitly permits and reports that fallback. Planning must reject a
mandatory capability the plugin cannot provide.

Portable compilers must advertise exact DTCS profiles, actions, functions,
operators, types, and modes. The compiler name alone never implies coverage.

### First-party portable policy (0.17)

Beginning with 0.17, every first-party ETLantic plugin that executes
dataframe, SQL, or Spark transformations ships a
portable transform compiler as well as its runtime integration. The compiler
may live in the same distribution or a clearly documented companion package,
but it must use the `etlantic.transform_compilers` entry point and pass the
public portable conformance suite for every advertised claim. Gate A of 0.17
made those claims inspectable through the capability matrix, `etlantic plugin
list` transform-compiler inventory, and guide-drift checks.

This is a first-party completeness policy, not a universal protocol
requirement. Third-party execution plugins may be native-only. Orchestrator,
scheduler, secret, storage, resource, observability, and model-bridge plugins
do not need portable transform compilers because they do not lower
transformations. A native-only plugin must omit the compiler entry point and
state the limitation explicitly.

Portable coverage is capability-based rather than all-or-nothing. First-party
plugins expand support by graduated DTCS family under the 0.17 Wave 1 / Wave 2
plan, and a family graduates only after normative semantics, shared fixtures,
and two independent conformant compilers exist. Until then, backend-specific
behavior stays available through native implementations. Families outside the
0.17 exit gate remain in 0.17 continuation.

## 5. Keep discovery deterministic and safe

After installing the package into a clean environment, verify discovery:

```bash
python -m pip install -e .
etlantic plugin list --kind dataframe --format json
```

The entry-point name is the stable engine key. Factories should return a new or
safely reusable protocol implementation and should not mutate process-global
registries. ETLantic registries are scoped to a planning/runtime context.

If one distribution supplies related extensions, declare each supported group:

```toml
[project.entry-points."etlantic.dataframe_plugins"]
acme = "etlantic_acme:create_plugin"

[project.entry-points."etlantic.transform_compilers"]
acme = "etlantic_acme:create_transform_compiler"
```

Do not make discovery depend on import order or manual registration.

For a first-party transformation runtime, CI must also assert that both the
runtime and compiler entry points are present in the built wheel. Future
first-party runtimes should start with the smallest conformant portable profile
instead of postponing all portable integration until after release.

## 6. Follow the security contract

Plugins execute trusted Python code and may cross data, credential, network,
and filesystem boundaries. Every plugin must follow these rules:

- Plans, reports, diagnostics, exceptions, and logs contain secret references,
  never resolved secret values.
- Discovery and planning perform no data writes and no credential resolution.
- Unsupported or untrusted behavior fails closed before mutation.
- External identifiers, paths, SQL, and generated code are validated and
  bounded before use.
- Cleanup runs on success, failure, timeout, and cancellation when the protocol
  owns resources.
- Schema history contains fingerprints and metadata only, never source rows.
- Production documentation shows an explicit, preferably version-pinned,
  `plugin_allowlist` entry.

For this example:

```python
from etlantic import production_profile

profile = production_profile(
    plugin_allowlist={"etlantic-acme": "==0.1.0"}
)
```

Test redaction with sentinel credentials and assert that the sentinel does not
appear in serialized plans, reports, diagnostics, logs, or exceptions.

## 7. Run conformance and integration tests

Use the matching public suite from `etlantic.testing`. A dataframe plugin's
minimum conformance test is:

```python
from etlantic.testing import run_conformance_suite
from etlantic_acme import create_plugin


def test_dataframe_conformance() -> None:
    rows = [{"customer_id": 1, "name": "Ada"}]
    run_conformance_suite(create_plugin(), engine="acme", sample_rows=rows)
```

Also test behavior the generic suite cannot know about:

- entry-point discovery in an installed wheel;
- every advertised capability and documented limitation;
- empty inputs, nulls, invalid rows, and multiple outputs;
- deterministic metadata and generated artifacts;
- timeouts, cancellation, retries, partial failures, and cleanup as applicable;
- backend version boundaries;
- secret redaction and failure before mutation;
- a small end-to-end pipeline using the public ETLantic API.

Run tests against the lowest and highest supported Python, ETLantic, and
backend versions. Build a wheel and test the wheel, not only an editable source
checkout:

```bash
python -m pytest
python -m build
python -m pip install --force-reinstall dist/etlantic_acme-*.whl
etlantic plugin list --format json
```

See [Testing Plugins](TESTING_PLUGINS.md) for every shipped suite.

## 8. Validate a representative pipeline

Plugin CI should exercise ETLantic's validate-first workflow against a fixture
pipeline. Validation and planning must not execute transformation code:

```bash
etlantic validate tests/fixtures/pipeline.py:ExamplePipeline \
  --profile tests/fixtures/profile.json --format json
etlantic plan tests/fixtures/pipeline.py:ExamplePipeline \
  --profile tests/fixtures/profile.json --format json
```

For CI annotations, also run:

```bash
etlantic validate tests/fixtures/pipeline.py:ExamplePipeline \
  --profile tests/fixtures/profile.json --format sarif
```

Orchestrator plugins should compile only a valid plan. Airflow-style compilers
generate artifacts; they do not execute the pipeline during compilation.

## 9. Document the compatibility contract

The package README must state:

- installation and supported Python versions;
- supported ETLantic minor range and protocol version;
- engine key and entry-point groups;
- exact capabilities and limitations;
- configuration and lifecycle behavior;
- production allowlist example;
- secret and trust boundaries;
- minimal authoring, validation, planning, and execution/compilation example;
- conformance suite and backend versions tested;
- support, changelog, and security-reporting links.

If the plugin implements ODCS, DTCS, or DPCS behavior, publish the supported
standard and schema versions. Keep release notes explicit about compatibility
or semantic changes.

## 10. Release independently

Before publishing:

1. run formatting, linting, type checks, unit tests, conformance tests, and the
   representative pipeline;
2. build both source and wheel distributions;
3. inspect the wheel for `py.typed`, README, license, and expected modules;
4. install the wheel in a clean environment and verify entry-point discovery;
5. verify a production profile accepts the documented name and version pin;
6. scan dependencies and confirm no credentials or generated local files are
   included;
7. publish release notes and the tested compatibility matrix.

Plugins use semantic versioning independently from ETLantic. A plugin does not
need to share ETLantic's version, but each release must constrain the ETLantic
versions it certifies.

## Definition of done

An ETLantic plugin is ready when all of the following are true:

- [ ] It implements a shipped public protocol without private imports.
- [ ] Its package uses a `src` layout and includes `py.typed`.
- [ ] Every discoverable extension uses the documented entry-point group and a
      zero-argument factory.
- [ ] Import and discovery have no external side effects.
- [ ] Identity, protocol version, package version, engine, and capabilities are
      accurate and deterministic.
- [ ] Unsupported mandatory behavior fails closed before mutation.
- [ ] Plans, reports, diagnostics, and logs are secret-free.
- [ ] The applicable public conformance suite passes.
- [ ] A first-party dataframe, SQL, or Spark transformation runtime also ships
      a discoverable portable compiler and passes portable conformance for each
      advertised claim.
- [ ] Advertised capabilities, lifecycle failures, and security boundaries have
      direct tests.
- [ ] A built wheel passes discovery and a representative validate/plan flow in
      a clean environment.
- [ ] The README publishes compatibility, limitations, trust configuration,
      and maintenance contacts.

Use the in-repository `etlantic-polars`, `etlantic-pandas`, `etlantic-sql`,
`etlantic-pyspark`, and `etlantic-airflow` packages as reference
implementations. If a reference package diverges from this guide, treat the
divergence as work to resolve rather than a new convention.

## Next step

Choose the protocol page for your category, implement the smallest complete
plugin, and make its conformance test pass before adding optional capabilities.
