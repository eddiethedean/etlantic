# Schema-registry protocol

> **Status: Supported in ETLantic 0.46.0** for the core
> `etlantic.schema-registry/1` protocol and in-memory registry.
> **Confluent HTTP is Experimental** (`etlantic-schemaregistry`) and is never
> Available in core.

Core stores **identity** only: subject, version, format, fingerprint, and
compatibility mode. Schema documents stay in the provider.

```python
from etlantic.streaming import InMemorySchemaRegistry, SchemaFormat, schema_fingerprint
from etlantic.testing import run_schema_registry_conformance_suite

run_schema_registry_conformance_suite()
```

## Production allowlist

`Profile.schema_registry_allowlist` is required in production. Empty or missing
pins fail closed (`PMREG140`). Example:

```json
{
  "schema_registry_allowlist": {
    "etlantic-schemaregistry": "==0.47.0"
  }
}
```

## Live adapter

`etlantic-schemaregistry` ships `FakeConfluentRegistry` for CI. Live Confluent
URLs (`ETLANTIC_SCHEMA_REGISTRY_URL`) are skipped unless operators opt in.
