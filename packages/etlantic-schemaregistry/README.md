# etlantic-schemaregistry (Experimental / Preview)

Version **0.51.0** (lockstep with ETLantic core).
Confluent-compatible schema-registry adapter over the core wire protocol.
Live Confluent HTTP is skipped unless `ETLANTIC_SCHEMA_REGISTRY_URL` is set.

**Maturity:** Experimental (Alpha classifier).

## Install

```bash
pip install 'etlantic-schemaregistry==0.51.0'
```

Core dependency: `etlantic>=0.51.0,<0.52`. Production profiles require
`Profile.schema_registry_allowlist`.
