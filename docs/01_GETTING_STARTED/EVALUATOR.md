# Evaluator Brief

A one-page answer for enterprise evaluators and technical decision-makers.

## Residual evaluation lead

| Topic | 0.25 |
|---|---|
| Maturity | **Beta** (PyPI) |
| Suitable for | Documented single-tenant pilots |
| Support | Community; **no formal SLA** |
| LTS | Current published minor only (`0.25.x`) |
| Not included | Multi-tenant control plane; unrestricted enterprise production |

## What ETLantic is

A typed, contract-driven **pipeline framework** for Python. You define
datasets, transformations, and pipelines once; ETLantic validates and plans
them; plugins execute.

It is **not** a dataframe engine, distributed scheduler, warehouse, or secret
manager.

## What is ready in bounded 0.25.0

| Area | Ready? |
|---|---|
| Typed authoring (`Data`, `Transformation`, `Pipeline`) | Yes |
| Functional builders / `PipelineDefinition` (`etlantic.authoring`) | Yes |
| Lossless `etlantic.pipeline/1` JSON TARGET | Yes |
| Authoring catalog + `EditCommand`s | Yes |
| Service facade (`etlantic.service`) | Yes |
| FastAPI reference adapter (`etlantic-fastapi`) | Yes (reference only; not 1.1 control plane) |
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
| Production GUI / multi-tenant control plane | No |

## Security posture

- Plans never contain resolved secrets
- SQL plugins use structured compilation with identifier/parameter safety;
  untrusted raw SQL is out of scope
- Spark session credentials resolve at acquire time and never embed in plans
- Plugin allowlists / version pins are **available** via
  `Profile.plugin_allowlist` (production profiles fail closed when empty)
- **0.20–0.21 trust controls shipped:** SafeIoPolicy, pre-import allowlist +
  manifests, artifact/cache isolation keys, outbound default-deny,
  unsafe-serialization prohibition, versioned `SecurityEvent`, release SBOM
  digests and GitHub attestations
- Report vulnerabilities privately; security fixes are supported on 0.25.x

### Shipped trust controls vs residual gaps

| Concern | Status |
|---|---|
| Secret-free plans/reports; `security_mode` | **Shipped** |
| Production plugin allowlist (selection, not sandbox) | **Shipped** |
| Safe I/O, outbound default-deny, serialization ban | **Shipped** |
| Artifact/cache isolation keys (single-tenant reference) | **Shipped** |
| Release SBOM digests + GitHub attestations | **Shipped** |
| Cross-tenant / multi-tenant isolation guarantees | **Residual / adopter-owned** |
| Formal DoS capacity SLA | **Residual** (partial I/O budgets only) |
| Compliance-grade audit system of record | **Adopter-owned** (CLI reports are operational evidence) |
| HA/DR, SOC2/GDPR certs, identity/RBAC/SSO | **Adopter-owned / out of scope** |
| In-process multi-tenancy | **Out of scope** — use process isolation |

Read [Security](../02_FOUNDATIONS/SECURITY.md) and the repository
[security policy](https://github.com/eddiethedean/etlantic/blob/main/SECURITY.md).
For the bounded reference topology and required controls, read
[Production Readiness](../06_EXECUTION/PRODUCTION_READINESS.md).

## Bounded production support (do not skip)

ETLantic **0.25.0** is a **Beta** (PyPI) release suitable for documented
single-tenant pilot deployments. Shipped trust controls do not make an
arbitrary multi-tenant topology safe.

Residual items that block **unrestricted** enterprise-wide production claims:

| Residual | Why it matters |
|---|---|
| Provenance beyond allowlist/pins + release attestations | Broader supply-chain programs remain adopter-owned |
| Cross-tenant artifact/cache isolation | Single-tenant isolation keys are not a multi-tenant control plane |
| Formal DoS budgets / capacity SLA | Partial I/O budgets only |
| Compliance audit SoR | Durable/file reports are operational evidence, not compliance |
| In-process multi-tenancy | Explicitly out of scope—use process isolation |

Treat CLI run reports under `.etlantic/reports/` as operational evidence (not
an audit system of record). Pass `--ephemeral` only when you want process-local
storage.

How to read status labels in deeper chapters:
[Documentation Status](../02_FOUNDATIONS/DOCUMENTATION_STATUS.md).

## What remains outside the Beta pilot envelope

- Copying long Airflow **design study** tutorials into production—use
  `examples/airflow_compile.py` and `etlantic-airflow` instead
- Treating Structured Streaming APIs as stable (they are experimental)
- AWS Secrets Manager / Vault (not shipped); OS keyring **is** available via
  `etlantic-keyring`
- Process-local / durable file reports as an audit system of record
- Stable 1.0 compatibility guarantees
- Managed Databricks/EMR/Connect Spark providers
- **Undocumented advanced portable profiles** — Polars and PySpark ship the
  documented 0.17 Wave 1 / Wave 2 families; Pandas and SQL remain at kernel +
  `portable-relational/1`. Continuation profiles remain outside the advertised
  claim set. Keep a native
  `@implementation(...)` for profiles outside the advertised claim set, or
  for `portable_transform_policy="native"`.

## Enterprise readiness matrix

| Concern | Status in 0.24 |
|---|---|
| License | MIT (core and official plugins) |
| Supported versions / EOL | Current Beta line is 0.25.x; see [SECURITY.md](https://github.com/eddiethedean/etlantic/blob/main/SECURITY.md) |
| Compliance attestations (SOC2, GDPR cert) | Adopter-owned — not provided |
| Identity / RBAC / SSO | Out of scope — use process and network isolation |
| HA / DR / RPO / RTO | Adopter-owned topology |
| SBOM / signed provenance | Release CI emits SPDX SBOM digests and GitHub build provenance attestations |
| Audit system of record | Gap — durable/file reports are operational evidence only |
| Tested scale | Local/pilot workloads; no published capacity guarantees |
| Upgrade / rollback | Pin exact versions; see [Migration 0.24 → 0.25](../11_DEVELOPMENT/MIGRATION_0_24_TO_0_25.md) |

## Recommended evaluation path

Follow this path **after** the green path (Install → Quickstart → First Pipeline
→ Engine selection), or as an enterprise diligence track:

1. [Installation](INSTALLATION.md) — `pip install etlantic==0.25.0`
2. [Quickstart](QUICKSTART.md) (`etlantic init`; `examples/` requires a checkout)
3. [First Pipeline](FIRST_PIPELINE.md)
4. [Engine selection](ENGINE_SELECTION.md)
5. [Capabilities](CAPABILITIES.md)
6. Optional Gate A: checkout
   [`examples/interchange_polars_pandas.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/interchange_polars_pandas.py)
   with `etlantic-polars` + `etlantic-pandas` at `==0.25.0`
7. Optional engine examples from a checkout (portable kernels, SQL, PySpark,
   Airflow compile, Prefect)
8. [Migration 0.24 → 0.25](../11_DEVELOPMENT/MIGRATION_0_24_TO_0_25.md) if
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
