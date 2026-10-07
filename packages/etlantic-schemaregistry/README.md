# etlantic-schemaregistry (Experimental / Preview)

Version **0.56.0** (lockstep with ETLantic core).
Confluent-compatible schema-registry adapter over the core wire protocol.
The read-only HTTP adapter fetches one bounded subject version from a
Confluent-compatible registry. It never registers schemas or stores documents
in inference observations.

**Maturity:** Experimental (Alpha classifier).

## Install

```bash
pip install 'etlantic-schemaregistry==0.56.1'
```

Core dependency: `etlantic>=0.56.0`. Production profiles require
`Profile.schema_registry_allowlist`.

```python
import etlantic as etl
from etlantic_schemaregistry import ConfluentHttpRegistry

registry = ConfluentHttpRegistry(
    "https://registry.example",
    allowed_hosts=("registry.example",),
)
result = etl.infer_registry_subject(registry, "orders-value", version=1)
```

The metadata adapter supports JSON Schema and Avro record fields. Protobuf
field inference returns an explicit unsupported diagnostic. Remote hosts must
be allowlisted; local HTTP is accepted for tests.
