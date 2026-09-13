# Migration 0.51 → 0.52

Pin core and first-party plugins to the 0.52.0 minor line. Plugin metadata now
requires `etlantic>=0.52.0,<0.53`.

```bash
python -m pip install 'etlantic==0.52.0' 'etlantic-polars==0.52.0'
```

Explicit profiles and `/1` plans remain compatible. To opt into adaptive
planning, set `execution_strategy="adaptive"`, declare ordered
`placement_targets`, and use `portable_transform_policy="require"`. The planner
returns a deterministic, inspectable `/2` plan; execution and external
compilation remain unavailable and fail closed with `PMADP500`.

Do not downgrade a stored `/2` document. Replan the source pipeline with an
explicit profile when a `/1` consumer is required. Keep production plugin,
optimization-pass, schema-registry, and resource-provider allowlists enabled.
