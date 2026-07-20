# Evaluator Brief

A one-page answer for enterprise evaluators and technical decision-makers.

## What ETLantic is

A typed, contract-driven **modeling** layer for data pipelines in Python. You
define datasets, transformations, and pipelines once; ETLantic validates and
plans them; plugins execute.

It is **not** a dataframe engine, distributed scheduler, warehouse, or secret
manager.

## What is stable in bounded 0.20.0

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
| DTCS 3.0 portable plan models/profiles | Yes (install `dtcs>=0.13,<1`; content floor `dtcs` 0.14.0) |
| `@Transformation.portable` authoring | Yes (0.11) |
| Portable Polars compiler (kernel + relational `/1`) | Yes (0.13+) |
| Portable PySpark compiler (kernel + relational `/1`) | Yes (0.13+) |
| Portable Pandas compiler (kernel + relational `/1`, eager) | Yes (0.14) |
| Portable SQL compiler (kernel + relational `/1`) | Yes (0.15) |
| Public portable transform conformance suite | Yes (0.14) |
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
- Report vulnerabilities privately; security fixes are supported on 0.21.x

Read [Security](../02_FOUNDATIONS/SECURITY.md) and the repository
[security policy](https://github.com/eddiethedean/etlantic/blob/main/SECURITY.md).
For the bounded reference topology and required controls, read
[Production Readiness](../06_EXECUTION/PRODUCTION_READINESS.md).

## Bounded production support (do not skip)

**ETLantic 0.21.0 is production/stable for documented single-tenant reference
deployments.** Plugin allowlists being “Available” do not make an arbitrary
topology safe.

The following residual gaps remain adopter-owned and block unrestricted
multi-tenant or enterprise-wide production claims:

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

## What remains outside the stable envelope

- Copying long Airflow **design study** tutorials into production—use
  `examples/airflow_compile.py` and `etlantic-airflow` instead
- Treating Structured Streaming APIs as stable (they are experimental)
- AWS Secrets Manager / Vault (not shipped); OS keyring **is** available via
  `etlantic-keyring`
- Process-local reports as an audit system of record
- Stable 1.0 compatibility guarantees
- Managed Databricks/EMR/Connect Spark providers
- **Undocumented advanced portable profiles** — Polars and PySpark ship the
  documented 0.17 Wave 1 / Wave 2 families; Pandas and SQL remain at kernel +
  `portable-relational/1`. Continuation profiles remain outside the advertised
  claim set. Keep a native
  `@implementation(...)` for profiles outside the advertised claim set, or
  for `portable_transform_policy="native"`.

## Enterprise readiness matrix

| Concern | Status in 0.20 |
|---|---|
| License | MIT (core and official plugins) |
| Supported versions / EOL | Current stable line is 0.21.x; see [SECURITY.md](https://github.com/eddiethedean/etlantic/blob/main/SECURITY.md) |
| Compliance attestations (SOC2, GDPR cert) | Adopter-owned — not provided |
| Identity / RBAC / SSO | Out of scope — use process and network isolation |
| HA / DR / RPO / RTO | Adopter-owned topology |
| SBOM / signed provenance | Release CI emits SPDX SBOM digests and GitHub build provenance attestations |
| Audit system of record | Gap — process-local reports are operational evidence only |
| Tested scale | Local/pilot workloads; no published capacity guarantees |
| Upgrade / rollback | Pin exact versions; see [Migration 0.19 → 0.20](../11_DEVELOPMENT/MIGRATION_0_19_TO_0_20.md) |

## Recommended evaluation path

Follow this path **after** the green path (Install → Quickstart → First Pipeline
→ Engine selection), or as an enterprise diligence track:

1. [Installation](INSTALLATION.md) — `pip install etlantic==0.21.0`
2. [Quickstart](QUICKSTART.md) (paste-ready; `examples/` requires a checkout)
3. [First Pipeline](FIRST_PIPELINE.md)
4. [Engine selection](ENGINE_SELECTION.md)
5. [Capabilities](CAPABILITIES.md)
6. Optional Gate A: checkout
   [`examples/interchange_polars_pandas.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/interchange_polars_pandas.py)
   with `etlantic-polars` + `etlantic-pandas` at `==0.21.0`
7. Optional engine examples from a checkout (portable kernels, SQL, PySpark,
   Airflow compile, Prefect)
8. [Migration 0.19 → 0.20](../11_DEVELOPMENT/MIGRATION_0_19_TO_0_20.md) if
   upgrading; otherwise [Upgrade hub](UPGRADE.md)
9. [Roadmap summary](../11_DEVELOPMENT/ROADMAP_SUMMARY.md) for sequencing
10. Production path: create `profiles/prod.json` from
    [CI starter](CAPABILITIES.md#ci-starter) /
    [prod.example.json](prod.example.json) and see
    [Production profiles](../06_EXECUTION/PRODUCTION_PROFILES.md)

## Support channel

GitHub issues for bugs and questions. Include ETLantic version, Python
version, and a minimal reproduction. Never include credentials or production
data. See [SUPPORT.md](https://github.com/eddiethedean/etlantic/blob/main/SUPPORT.md).
