# Evaluator Brief

A one-page answer for enterprise evaluators and technical decision-makers.

## What ETLantic is

A typed, contract-driven **modeling** layer for data pipelines in Python. You
define datasets, transformations, and pipelines once; ETLantic validates and
plans them; plugins execute.

It is **not** a dataframe engine, distributed scheduler, warehouse, or secret
manager.

## What is ready in alpha 0.13.0

| Area | Ready? |
|---|---|
| Typed authoring (`Data`, `Transformation`, `Pipeline`) | Yes |
| Validation and secret-free `PipelinePlan` | Yes |
| ODCS / DTCS / DPCS interchange | Yes |
| Local in-process runtime + run reports | Yes |
| Memory / callable / JSON / CSV / no-write storage | Yes |
| Env + mounted-file secrets | Yes |
| Polars / Pandas plugins | Yes (separate packages) |
| SQL plugin (`etlantic-sql`) | Yes (PostgreSQL reference) |
| PySpark plugin (`etlantic-pyspark`) | Yes (local provider; batch production path) |
| Structured Streaming | Experimental |
| Airflow / orchestrator compilation | Yes (`etlantic-airflow`) |
| DTCS 3.0 portable plan models/profiles | Yes (`dtcs>=0.13`) |
| `@Transformation.portable` authoring | Yes (0.11) |
| Portable Polars compiler (kernel + relational `/1`) | Yes (0.13) |
| Portable PySpark compiler (kernel + relational `/1`) | Yes (0.13) |
| Portable Pandas / SQL compilers | No (0.14–0.15) |
| Multi-tenant durable orchestration | No |
| Formal SLA / support response times | No |

## Security posture

- Plans never contain resolved secrets
- SQL plugins use structured compilation with identifier/parameter safety;
  untrusted raw SQL is out of scope
- Spark session credentials resolve at acquire time and never embed in plans
- Plugin allowlists / version pins are **available** in 0.9+ via
  `Profile.plugin_allowlist` (production profiles fail closed when empty)
- Threat model documents residual Gaps (provenance, artifact/cache isolation,
  DoS budgets, outbound constraints, unsafe-serialization prohibition)
- Report vulnerabilities privately; alpha has best-effort fixes only

Read [Security](../02_FOUNDATIONS/SECURITY.md) and the repository
[security policy](https://github.com/eddiethedean/etlantic/blob/main/SECURITY.md).
For a bounded pilot topology and required controls, read
[Production Readiness](../06_EXECUTION/PRODUCTION_READINESS.md).

## Production readiness gate (do not skip)

**ETLantic 0.13.0 is alpha.** Plugin allowlists being “Available” does **not**
mean the product is production-ready.

Do **not** productionize until the security release gate closes (targeted for
1.0). Residual Gaps that still block a production claim include:

| Gap (from Security Evaluation) | Why it matters |
|---|---|
| Plugin provenance beyond allowlist/pins | Supply-chain attestation incomplete |
| Artifact and cache isolation | Cross-run / cross-tenant exposure risk |
| Outbound destination constraints | SSRF / exfiltration controls incomplete |
| Denial-of-service budgets | Unbounded planning/load work |
| Unsafe serialization prohibition | Deserialization attack surface |
| In-process multi-tenancy | Explicitly out of scope—use process isolation |

Treat process-local run reports as operational evidence for a single process,
not an audit system of record.

How to read status labels in deeper chapters:
[Documentation Status](../02_FOUNDATIONS/DOCUMENTATION_STATUS.md).

## What not to bet on yet

- Copying long Airflow **design study** tutorials into production—use
  `examples/airflow_compile.py` and `etlantic-airflow` instead
- Treating Structured Streaming APIs as stable (they are experimental)
- AWS Secrets Manager / Vault (not shipped); OS keyring **is** available via
  `etlantic-keyring`
- Process-local reports as an audit system of record
- Stable 1.0 compatibility guarantees
- Managed Databricks/EMR/Connect Spark providers
- **Portable compilers beyond relational `/1`** — Pandas and SQL compilers
  remain planned for 0.14–0.15. Polars and PySpark claim kernel +
  `portable-relational/1` in 0.13; keep a native `@implementation(...)` for
  profiles outside that claim set, or for `portable_transform_policy="native"`.

## Enterprise readiness matrix

| Concern | Status in 0.13 |
|---|---|
| License | MIT (core and official plugins) |
| Supported versions / EOL | Best-effort on current alpha line; see [SECURITY.md](https://github.com/eddiethedean/etlantic/blob/main/SECURITY.md) |
| Compliance attestations (SOC2, GDPR cert) | Adopter-owned — not provided |
| Identity / RBAC / SSO | Out of scope — use process and network isolation |
| HA / DR / RPO / RTO | Adopter-owned topology |
| SBOM / signed provenance | Gap — not yet emitted by release automation |
| Audit system of record | Gap — process-local reports are operational evidence only |
| Tested scale | Local/pilot workloads; no published capacity guarantees |
| Upgrade / rollback | Pin exact versions; see [Migration 0.11 → 0.12](../11_DEVELOPMENT/MIGRATION_0_11_TO_0_12.md) |

## Recommended evaluation path

1. [Installation](INSTALLATION.md) — `pip install etlantic==0.13.0`
2. [Quickstart](QUICKSTART.md) or `examples/quickstart.py`
3. [Capabilities](CAPABILITIES.md)
4. Optional: `examples/portable_polars_kernel.py` with `etlantic-polars`
5. Optional: `examples/dataframe_parity.py` with Polars or Pandas
6. Optional: `examples/sql_to_sql.py` (and other `examples/sql_*.py`) with
   `etlantic-sql`
7. Optional: `examples/pyspark_local.py` with `etlantic-pyspark`
8. Optional: `examples/airflow_compile.py` with `etlantic-airflow`
9. Optional: SparkForge adapter via `uv sync --group sparkforge`
10. [Migration 0.11 → 0.12](../11_DEVELOPMENT/MIGRATION_0_11_TO_0_12.md) if
    upgrading from 0.11
11. [Roadmap](../11_DEVELOPMENT/ROADMAP.md) for sequencing

## Support channel

GitHub issues for bugs and questions. Include ETLantic version, Python
version, and a minimal reproduction. Never include credentials or production
data. See [SUPPORT.md](https://github.com/eddiethedean/etlantic/blob/main/SUPPORT.md).
