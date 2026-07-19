# Operations Examples

> **Status: Available in ETLantic 0.18.0.** Minimal patterns for secrets,
> schema drift, and CI SARIF — beside the green path.

## Secrets (runtime references only)

Never put secret values in plans, reports, or contracts. Use `SecretRef` and
a provider (env/file, or `etlantic-keyring`).

```python
from etlantic import SecretRef

db_password = SecretRef(provider="env", key="ETLANTIC_DB_PASSWORD")
```

See [Secrets Management](../06_EXECUTION/SECRETS_MANAGEMENT.md) and
[Optional packages](../10_REFERENCE/OPTIONAL_PACKAGES.md) (`etlantic-keyring`).

## Schema drift (observe / acknowledge)

Schema history stores fingerprints and metadata — never source rows.

```bash
etlantic schema inspect path.py:MyContract --format json
etlantic schema check path.py:MyContract --format json
etlantic schema history --format json
```

See CLI `etlantic schema --help` and
[Known limitations](../10_REFERENCE/KNOWN_ISSUES.md).

## SARIF in CI

```bash
etlantic validate path/to/pipeline.py:MyPipeline \
  --profile ./profiles/prod.json \
  --format sarif > etlantic.sarif
```

Production profiles require a non-empty `plugin_allowlist`. Starter JSON:
[CI starter](CAPABILITIES.md#ci-starter) / [prod.example.json](prod.example.json)
(not installed with the PyPI wheel—create `profiles/prod.json` yourself). See
[CI integration](../06_EXECUTION/CI_INTEGRATION.md).

## Related

- [Production profiles](../06_EXECUTION/PRODUCTION_PROFILES.md)
- [Production readiness](../06_EXECUTION/PRODUCTION_READINESS.md)
- [Multi-file sample](../09_EXAMPLES/SAMPLE_PROJECT.md)
