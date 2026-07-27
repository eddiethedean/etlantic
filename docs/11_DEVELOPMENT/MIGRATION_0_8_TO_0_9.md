# Migrating from 0.8 to 0.9

ETLantic 0.9 focuses on **tooling, SDK polish, and ecosystem readiness**.
Orchestration protocols from 0.8 are unchanged; 0.9 wraps them with CLI,
diagnostics, plugin trust, and optional packages.

## What changed

- CLI: `compile`, `generate`, `diff`, `plugin`, `schema *`, `reliability *`,
  `viz *`, and `report compare` (JSON / human / SARIF where applicable)
- `Profile.plugin_allowlist` with version pins; production profiles fail closed
- `FileSchemaHistoryProvider` under `.etlantic/schema-history/`
- SARIF + GitHub annotation renderers (`etlantic.diagnostics.sarif`)
- Reliability provider protocols and ops CLI
- `FileReportStore` + report compare
- Visualization: Graphviz DOT, HTML lineage pages, JSON lineage export
- Optional packages: `etlantic-keyring`, `etlantic-sqlmodel`
- Optional extra `etlantic[otel]` for OpenTelemetry adapter
- IDE command/result JSON schemas (`etlantic.ide`)
- Notebook display helpers and agent guidance generators
- Plugin packages bump to `0.9.0` and require `etlantic>=0.9.0,<1.0`

## Install

```bash
pip install --upgrade 'etlantic>=0.9.0'
pip install etlantic-keyring      # optional OS keyring secrets
pip install etlantic-sqlmodel     # optional SQLModel bridge
# or extras:
pip install 'etlantic[keyring,sqlmodel,otel,airflow]'
```

## Plugin trust

```python
from etlantic import Profile

profile = Profile(
    name="production",
    security_mode="production",  # required for fail-closed trust
    security_domain="production",
    plugin_allowlist={
        "etlantic-polars": ">=0.9.0,<1.0",
        "etlantic-airflow": ">=0.9.0,<1.0",
    },
)
```

Unlisted plugins are rejected in production profiles.

## CLI examples

```bash
etlantic validate module:MyPipeline --format sarif
etlantic compile module:MyPipeline --target airflow -o dags/
etlantic generate module:MyPipeline -o contracts/
etlantic schema monitor module:MyContract --subject orders
etlantic viz html module:MyPipeline -o lineage.html
```

## Unchanged

- `compile_plan` / `etlantic-airflow` orchestration model
- Spark / SQL / dataframe execution protocols
- Local orchestrator default

## See also

- [Current Capabilities](../01_GETTING_STARTED/CAPABILITIES.md)
- [CHANGELOG](https://github.com/eddiethedean/etlantic/blob/main/CHANGELOG.md)
