# Compatibility Matrix

This table describes the declared compatibility of ETLantic 0.13.0.

| Surface | Supported range or version |
|---|---|
| Python | 3.11, 3.12, 3.13 |
| Pydantic | `>=2.12,<3` |
| ContractModel | `>=0.1.2` |
| DTCS specification | `3.0.0` (`dtcsVersion: "3.0.0"`; 2.0.0 / 1.0.0 remain readable) |
| DTCS toolkit | `>=0.13,<1` |
| DPCS toolkit | `>=0.13,<1` |
| Pipeline plan schema | `etlantic.plan/1` |
| Dataframe protocol | `etlantic.dataframe/1` |
| SQL protocol | `etlantic.sql/1` |
| Polars plugin | `etlantic-polars==0.13.0` |
| Pandas plugin | `etlantic-pandas==0.13.0` |
| SQL plugin | `etlantic-sql==0.13.0` |
| PySpark plugin | `etlantic-pyspark==0.13.0` |
| Airflow plugin | `etlantic-airflow==0.13.0` |
| Keyring provider | `etlantic-keyring==0.13.0` |
| SQLModel bridge | `etlantic-sqlmodel==0.13.0` |
| SparkForge adapter | `etlantic-sparkforge==0.13.0` |
| Orchestration protocol | `etlantic.orchestration/1` |
| DTCS Transformation Plan protocol | Published in DTCS 3.0 / `dtcs` 0.13 as `dtcs.transform-plan/2` (v1 readable); ETLantic authoring shipped in 0.11 |
| Portable authoring profile | Shipped as `etlantic.transform/1` (full DTCS 3.0 facade→IR authoring) |
| Portable compiler protocol | Shipped as `etlantic.transform-compiler/1` (Polars + PySpark relational in 0.13) |
| Package stability | Alpha |
| Plugin SDK stability | Protocol stable within 0.8; third-party SDK still evolving |

## Portable transformation profiles

DTCS publication does not mean the ETLantic facade or plugin compilers are
already implemented. Compatibility is tracked independently:

| DTCS profile | Spec status | ETLantic authoring (0.11) | ETLantic compilers |
|---|---|---|---|
| `dtcs:profile/portable-relational-kernel/1` | Published (2.0) | shipped (authoring) | shipped (Polars + PySpark, 0.12/0.13) |
| `dtcs:profile/portable-relational/1` | Published (2.0) | shipped (authoring) | shipped (Polars + PySpark, 0.13) |
| `dtcs:profile/portable-window/1` | Experimental (2.0) | shipped (alias authoring) | 0.15+ two-compiler graduation |
| `dtcs:profile/portable-complex-types/1` | Experimental (2.0) | shipped (alias authoring) | 0.15+ two-compiler graduation |
| `dtcs:profile/portable-relational-kernel/2` | Candidate (3.0) | shipped (authoring, plan v2) | shipped (plan-v2 metadata via Polars kernel, 0.12) |
| `dtcs:profile/portable-relational/2` | Candidate (3.0) | shipped (authoring) | metadata alias of `/1` on Polars + PySpark (0.13); no candidate extensions |
| `dtcs:profile/portable-string-advanced/1` | Experimental (3.0) | shipped (authoring) | 0.15+ graduation |
| `dtcs:profile/portable-conversion/1` | Experimental (3.0) | shipped (authoring) | 0.15+ graduation |
| `dtcs:profile/portable-statistics/1` | Experimental (3.0) | shipped (authoring) | 0.15+ graduation |
| `dtcs:profile/portable-complex-values/1` | Experimental (3.0) | shipped (authoring) | 0.15+ graduation |
| `dtcs:profile/portable-reshape/1` | Experimental (3.0) | shipped (authoring) | 0.15+ graduation |
| `dtcs:profile/portable-relational-extended/1` | Experimental (3.0) | shipped (authoring) | 0.15+ graduation |
| `dtcs:profile/portable-temporal-iana/1` | Experimental (3.0) | shipped (authoring) | 0.15+ graduation |
| `dtcs:profile/portable-nondeterministic/1` | Experimental (3.0) | shipped (authoring) | 0.15+ graduation |
| `dtcs:profile/portable-window/2` | Candidate (3.0) | shipped (authoring) | 0.15+ graduation |

See [Capabilities](../01_GETTING_STARTED/CAPABILITIES.md) and the
[DTCS 3.0 publication record](../11_DEVELOPMENT/DTCS_3_0_SPEC_PROPOSAL.md).
