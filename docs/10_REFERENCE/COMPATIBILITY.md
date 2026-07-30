# Compatibility Matrix

This table describes the declared compatibility of ETLantic 0.35.0.

| Surface | Supported range or version |
|---|---|
| Python | 3.11, 3.12, 3.13 |
| Pydantic | `>=2.12,<3` |
| ContractModel | `>=0.2,<0.3` ([ODCS](../03_DATA_CONTRACTS/ODCS.md) `v3.1.0`) |
| [DTCS](../04_TRANSFORMATIONS/DTCS.md) specification | `3.0.0` (`dtcsVersion: "3.0.0"`; 2.0.0 / 1.0.0 remain readable) |
| DTCS toolkit | `>=0.13,<1` |
| [DPCS](../05_PIPELINES/DPCS.md) toolkit | `>=0.13,<1` |
| Pipeline plan schema | `etlantic.plan/1` |
| Pipeline authoring wire | `etlantic.pipeline/1` |
| Run report wire | `etlantic.run_report/1` |
| Capabilities vocabulary | `etlantic.capabilities/1` |
| Dataframe protocol | `etlantic.dataframe/1` |
| Tabular interchange (Gate A) | `etlantic.interchange/1` — Polars ↔ Pandas only; see [API Plan/Runtime](API_PLAN_RUNTIME.md#gate-a-tabular-interchange-etlanticinterchange1) |
| SQL protocol | `etlantic.sql/1` |
| Spark protocol | `etlantic.spark/1` |
| Polars plugin | `etlantic-polars==0.35.0` |
| Pandas plugin | `etlantic-pandas==0.35.0` |
| SQL plugin | `etlantic-sql==0.35.0` |
| PySpark plugin | `etlantic-pyspark==0.35.0` |
| Airflow plugin | `etlantic-airflow==0.35.0` |
| Prefect scheduler | `etlantic-prefect==0.35.0` |
| Keyring provider | `etlantic-keyring==0.35.0` |
| SQLModel bridge | `etlantic-sqlmodel==0.35.0` |
| FastAPI reference adapter | `etlantic-fastapi==0.35.0` (reference only; not a control plane; see the [planned first-class control-plane program](../11_DEVELOPMENT/MULTI_TENANT_CONTROL_PLANE_PLAN.md)) |
| Medallantic (facade) | `medallantic==0.35.0` |
| SparkForge redirect | `etlantic-sparkforge==0.35.0` (compatibility shim; prefer `medallantic`) |
| DataFusion plugin | `etlantic-datafusion==0.35.0` (**Experimental** Gate B stub; no graduated claims) |
| Orchestration protocol | `etlantic.orchestration/1` |
| DTCS Transformation Plan protocol | Published in DTCS 3.0 / `dtcs` 0.13 as `dtcs.transform-plan/2` (v1 readable); ETLantic authoring shipped in 0.11 |
| Portable authoring profile | Shipped as `etlantic.transform/1` (full DTCS 3.0 facade→IR authoring) |
| Portable compiler protocol | Shipped as `etlantic.transform-compiler/1` (Polars + PySpark + Pandas relational in 0.13–0.14) |
| Package stability | Beta — suitable for documented single-tenant reference deployments (not unrestricted enterprise production) |
| Plugin SDK stability | Protocol `/1` families **frozen** in 0.28.0; third-party plugins must pin `etlantic>=0.35.0,<0.36` and re-run conformance |

## Tested versus declared

The core CI matrix runs linting and the core test suite on Ubuntu, Windows, and
macOS with Python 3.11, 3.12, and 3.13. This is the broadest tested platform
surface for 0.35.0. Quadruple-minor wire codec burn-in covers the
0.24→0.25→0.26→0.27→0.28 upgrade window; see
[Wire schema ranges](WIRE_SCHEMA_RANGES.md).

Optional plugin jobs run primarily on Ubuntu with Python 3.11. Polars and
Pandas each have dedicated dataframe/compiler/conformance jobs. SQL runs
against SQLite and PostgreSQL 16. PySpark compiler and differential coverage
uses the sparkless compatibility backend by default; real JVM PySpark checks
run in the dedicated `real-pyspark` CI job (0.23). Airflow compile import is
tested across 2.8.x–2.10.x via `airflow-runtime`; Prefect, keyring, SQLModel,
and SparkForge also have dedicated Ubuntu/3.11 jobs. Microbenchmark regression
gate runs on Ubuntu/3.11 (`scripts/check_benchmarks.py`).

Package metadata declares these backend dependency ranges:

| Package or extra | Declared backend range |
|---|---|
| `etlantic-polars` | `polars>=1.0,<2`; optional `pyarrow>=14` |
| `etlantic-pandas` | `pandas>=2.2,<3`; optional `pyarrow>=14` |
| `etlantic-pyspark` | `pyspark>=3.5,<4`; optional `delta-spark>=3.0,<4` |
| `etlantic-sql` | `sqlalchemy>=2.0,<3`, `psycopg[binary]>=3.1,<4` |
| `etlantic-sqlmodel` | `sqlmodel>=0.0.22,<1` |
| `etlantic-keyring` | `keyring` (no narrower range declared) |
| `etlantic-airflow` | No Apache Airflow runtime dependency; it compiles DAG source |
| `airflow-runtime` (uv group, 0.23) | `etlantic-airflow` only; CI installs `apache-airflow` 2.8.x–2.10.x separately for import matrix |
| `etlantic-prefect` | `prefect>=3,<4` |
| `etlantic[otel]` / `[observability]` | `opentelemetry-api>=1.36,<2` |
| `etlantic[arrow]` | `pyarrow>=14` |

A declared range means the resolver may install that version; it does not mean
every backend version and operating system combination is exercised in CI.
For a controlled deployment, test the exact resolved environment and pin
`etlantic==0.35.0` plus every official plugin to `==0.35.0`.

Core extras already enforce exact official plugin versions, for example
`etlantic[polars]==0.35.0` depends on `etlantic-polars==0.35.0`. Official
plugin source metadata accepts core `etlantic>=0.35.0,<0.36`, which is
minor-matched but less exact. Published, older, or third-party plugin metadata
may use a broader bound such as `etlantic>=0.14,<1.0`; do not treat that broad
specifier as evidence of tested cross-minor compatibility. Match the core and
official plugin minor versions, and prefer exact pins for reproducibility.

Root import changes in 0.28 (third-wave removals of demoted aliases): see
[Migration 0.27 → 0.28](../11_DEVELOPMENT/MIGRATION_0_27_TO_0_28.md).
Package inventory: [Optional packages](OPTIONAL_PACKAGES.md).

## Portable transformation profiles

DTCS publication does not mean the ETLantic facade or plugin compilers are
already implemented. Compatibility is tracked independently:

| DTCS profile | Spec status | ETLantic authoring (0.11) | ETLantic compilers |
|---|---|---|---|
| `dtcs:profile/portable-relational-kernel/1` | Published (2.0) | shipped (authoring) | shipped (Polars + PySpark + Pandas, 0.12–0.14) |
| `dtcs:profile/portable-relational/1` | Published (2.0) | shipped (authoring) | shipped (Polars + PySpark + Pandas, 0.13–0.14) |
| `dtcs:profile/portable-window/1` | Experimental (2.0) | shipped (alias authoring) | shipped (Polars + PySpark, 0.17 Gate B) |
| `dtcs:profile/portable-complex-types/1` | Experimental (2.0) | shipped (alias authoring) | shipped (Polars + PySpark, 0.17 Gate C) |
| `dtcs:profile/portable-relational-kernel/2` | Candidate (3.0) | shipped (authoring, plan v2) | shipped (plan-v2 metadata via Polars kernel, 0.12) |
| `dtcs:profile/portable-relational/2` | Candidate (3.0) | shipped (authoring) | metadata alias of `/1` on Polars + PySpark + Pandas (0.13–0.14); no candidate extensions |
| `dtcs:profile/portable-string-advanced/1` | Experimental (3.0) | shipped (authoring) | shipped (Polars + PySpark, 0.17 Gate B) |
| `dtcs:profile/portable-conversion/1` | Experimental (3.0) | shipped (authoring) | shipped (Polars + PySpark, 0.17 Gate B) |
| `dtcs:profile/portable-statistics/1` | Experimental (3.0) | shipped (authoring) | shipped (Polars + PySpark, 0.17 Gate B) |
| `dtcs:profile/portable-complex-values/1` | Experimental (3.0) | shipped (authoring) | shipped (Polars + PySpark, 0.17 Gate C) |
| `dtcs:profile/portable-reshape/1` | Experimental (3.0) | shipped (authoring) | shipped (Polars + PySpark, 0.17 Gate C) |
| `dtcs:profile/portable-relational-extended/1` | Experimental (3.0) | shipped (authoring) | 0.17 continuation |
| `dtcs:profile/portable-temporal-iana/1` | Experimental (3.0) | shipped (authoring) | 0.17 continuation |
| `dtcs:profile/portable-nondeterministic/1` | Experimental (3.0) | shipped (authoring) | 0.17 continuation (policy-gated) |
| `dtcs:profile/portable-window/2` | Candidate (3.0) | shipped (authoring) | 0.17 continuation |

See [Capabilities](../01_GETTING_STARTED/CAPABILITIES.md) and the
[DTCS 3.0 publication record](../11_DEVELOPMENT/DTCS_3_0_SPEC_PROPOSAL.md).
