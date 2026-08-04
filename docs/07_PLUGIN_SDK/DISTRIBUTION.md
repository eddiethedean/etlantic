# Distribution

> **Status: Available in ETLantic 0.43.0.**

Distribution describes how ETLantic plugins are packaged, published,
discovered, installed, and maintained across the ecosystem.

A healthy plugin ecosystem depends on stable distribution practices. Plugins
should be independently releasable while remaining compatible with the
ETLantic Plugin SDK and supported standards.

## Goals

Plugin distribution should:

- Support independent releases.
- Encourage semantic versioning.
- Make installation simple.
- Preserve compatibility metadata.
- Enable automated discovery.
- Support community and commercial plugins.

## Philosophy

The ETLantic core should remain small.

Functionality grows through independently distributed plugins.

```text
ETLantic Core
        │
        ▼
 Python Package Index
        │
 ┌──────┼─────────────────────────┐
 ▼      ▼         ▼              ▼
Execution Dataframe Storage   Resource
 Plugins   Plugins  Plugins   Providers
```

## Packaging

Plugins should be distributed as standard Python packages.

### Published packages (0.24)

Install matching minors throughout ETLantic's 0.x roadmap:

- `etlantic-polars`
- `etlantic-pandas`
- `etlantic-sql`
- `etlantic-pyspark`
- `etlantic-airflow`
- `etlantic-prefect`
- `etlantic-keyring`
- `etlantic-sqlmodel`
- `medallantic`
- `etlantic-datafusion` (experimental Gate B stub)
- `etlantic-fastapi` (CP1 `ETLanticAPI` + thin non-CP `create_reference_app`;
  CP1 ≠ production multi-tenant GA)

### Naming convention (examples only — not published)

Third-party and future plugins should follow a consistent naming pattern.
These names are **illustrative only** and are **not** available on PyPI today:

- `etlantic-postgres`
- `etlantic-secrets-aws`
- `etlantic-secrets-azure`
- `etlantic-secrets-gcp`
- `etlantic-secrets-vault`

First-party **Experimental** connector packages (in-tree; Alpha fake/CI — not
Supported) ship as real workspace packages:

- `etlantic-s3`
- `etlantic-iceberg`
- `etlantic-snowflake`

## Installation

Typical installation:

```bash
pip install etlantic-airflow
```

Multiple plugins may be installed simultaneously.

Profiles determine which plugins are used.

## Discovery

Installed plugins are discoverable through domain-specific helpers (no global
registry class):

```python
from etlantic.dataframe import discover_dataframe_plugins
from etlantic.orchestration import discover_orchestrator_plugins
from etlantic.spark import discover_spark_plugins, discover_spark_providers
from etlantic.sql import discover_sql_plugins

dataframe_plugins = discover_dataframe_plugins()
sql_plugins = discover_sql_plugins()
spark_plugins = discover_spark_plugins()
spark_providers = discover_spark_providers()
orchestrators = discover_orchestrator_plugins()
```

CLI: `etlantic plugin list`. Discovery does not require manual registration in
normal deployments. Secret providers are attached to the runtime / profile.

## Compatibility Metadata

Every plugin should publish:

- Plugin name
- Plugin version
- Supported ETLantic version(s)
- Supported SDK version
- Supported [ODCS](../03_DATA_CONTRACTS/ODCS.md) version(s)
- Supported [DTCS](../04_TRANSFORMATIONS/DTCS.md) version(s)
- Supported [DPCS](../05_PIPELINES/DPCS.md) version(s)
- Capability declarations

Planning uses this metadata when selecting plugins.

## Semantic Versioning

Plugins should follow Semantic Versioning.

- MAJOR — breaking SDK or behavior changes
- MINOR — backward-compatible features
- PATCH — bug fixes and non-semantic improvements

## Release Workflow

Recommended workflow:

1. Implement
2. Test
3. Run SDK conformance suite
4. Publish package
5. Publish release notes
6. Update compatibility matrix

## Dependency Management

Plugins should minimize dependencies and isolate backend-specific libraries.

Optional dependencies should be preferred where practical to avoid unnecessary
install size for users who do not need every backend.

## Security

Plugin authors should:

- Sign releases when possible.
- Keep dependencies updated.
- Avoid embedding credentials.
- Follow secure disclosure practices.
- Publish supported version ranges.
- Ensure secret-provider packages pass redaction, rotation, lease, and
  sentinel-leak conformance tests.

## Compatibility report

Independently installed plugins can check compatibility without private
modules:

```bash
etlantic plugin compatibility etlantic-polars --format json
etlantic plugin compatibility --format human
```

The report compares the plugin's static `etlantic-plugin-manifest.json` and
packaging metadata against the installed core: protocol ranges, capability
vocabulary (`etlantic.capabilities/1`), plan schema (`etlantic.plan/1`),
Requires-Python, the plugin's `etlantic` pin, and (with `--profile`) allowlist
status. Findings use `PMPLUG44x` codes and fail closed on mismatch.

## Best Practices

- Keep plugins independently releasable.
- Publish clear compatibility metadata.
- Run `etlantic plugin compatibility` in plugin CI against the supported core range.
- Use semantic versioning.
- Ship documentation with every release.
- Maintain changelogs.

## Anti-Patterns

Avoid:

- Bundling all plugins into the core package.
- Publishing plugins without compatibility metadata.
- Introducing breaking changes in minor releases.
- Hiding runtime dependencies.
- Depending on internal ETLantic APIs.

## Key Principle

> ETLantic grows through a distributed ecosystem of independently versioned
> plugins. Stable packaging, discovery, and compatibility metadata allow users
> to compose the execution environment that best fits their pipelines.

## Next Step

Continue with the [Examples](../09_EXAMPLES/README.md) section to see plugins
used in complete pipelines.
