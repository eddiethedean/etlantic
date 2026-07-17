# Migrating from 0.10 to 0.11

ETLantic 0.11 ships **portable authoring** (`@Transformation.portable`,
`etlantic.transform` → `dtcs.transform-plan/2`) plus bug fixes for production
plugin trust and schema-type aliases. Portable **compilers** remain 0.12–0.15.

## What changed

- Package and plugin versions advance to `0.11.0` (`etlantic>=0.11.0,<1.0`)
- DTCS toolkit floor raised to `dtcs>=0.13`
- `@Transformation.portable` / `etlantic.transform` authoring APIs
- `Transformation.to_transform_plan()` / `portable_fingerprint()`
- Production `plugin_allowlist` enforced on validate / run / compile
- Bare version pins in allowlists accepted as `==version`
- Declared vs observed schema types canonicalize (`int`≡`integer`, etc.)
- Portable IR fixes (unique action IDs, string sort keys, window propagation)

## Install

```bash
pip install --upgrade 'etlantic>=0.11.0'
# Optional plugins (same minor):
pip install --upgrade 'etlantic-polars==0.11.0'  # or pandas/sql/pyspark/airflow/...
```

## Portable authoring (new)

You may author relational behavior once:

```python
from etlantic.transform import functions as F

@NormalizeCustomers.portable
def normalize(customers, minimum_age):
    return customers.filter(F.col("age") >= minimum_age)
```

Inspect the plan with `NormalizeCustomers.to_transform_plan()`. **Execution
still requires** `@NormalizeCustomers.implementation(...)` until compilers
ship. See [Portable Transformations](../04_TRANSFORMATIONS/PORTABLE_TRANSFORMATIONS.md).

## Production profiles

Empty `Profile.plugin_allowlist` on production profiles now fails validation
and run (`PMPLUG401`). Set an explicit allowlist before upgrading production
pilots:

```python
Profile(
    name="production",
    security_domain="production",
    plugin_allowlist={"local": None, "etlantic-polars": ">=0.11.0,<1.0"},
)
```

## Unchanged

- Local / Polars / Pandas / SQL / PySpark / Airflow plugin protocols
- SparkForge adapter package (version-aligned to 0.11)
- CLI command set from 0.9–0.10

## See also

- [Current Capabilities](../01_GETTING_STARTED/CAPABILITIES.md)
- [Migration 0.9 → 0.10](MIGRATION_0_9_TO_0_10.md)
- [CHANGELOG](https://github.com/eddiethedean/etlantic/blob/main/CHANGELOG.md)
