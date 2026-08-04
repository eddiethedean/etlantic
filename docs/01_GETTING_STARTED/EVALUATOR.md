# Evaluator Brief

> **Status: Available in ETLantic 0.44.0.**

A one-page answer for enterprise evaluators and technical decision-makers.

!!! note "Plans ≠ product"
    Maintainer roadmap / multi-tenant plans under Contribute are **not**
    shipped product claims. Judge the product from this brief, [Capabilities](CAPABILITIES.md),
    and the green path — not from future gate documents.
    **CP1–CP4 alone ≠ GA**; **0.43** graduated Supported profiles.

## Residual evaluation lead

| Topic | 0.44 |
|---|---|
| Maturity | **Beta** (PyPI) |
| Suitable for | Documented single-tenant pilots; Supported multi-tenant profiles |
| Support | Community; **no formal SLA** |
| LTS | Current published minor only (`0.44.x`) |
| Not included as GA | Unbounded scale; formal enterprise SLA; `shared-service` without real RLS |

## What ETLantic is

A typed, contract-driven **pipeline framework** for Python. You define
datasets, transformations, and pipelines once; ETLantic validates and plans
them; plugins execute.

It is **not** a dataframe engine, distributed scheduler, warehouse, or secret
manager.

## What is ready in bounded 0.44.0

| Area | Ready? |
|---|---|
| Typed authoring (`Data`, `Transformation`, `Pipeline`) | Yes |
| Functional builders / `PipelineDefinition` (`etlantic.authoring`) | Yes |
| Lossless `etlantic.pipeline/1` JSON TARGET | Yes |
| Authoring catalog + `EditCommand`s | Yes |
| Service facade (`etlantic.service`) | Yes |
| FastAPI dual surface (`etlantic-fastapi`) | Yes — CP1 `ETLanticAPI` + thin `create_reference_app` (CPn alone ≠ GA; use Supported profiles) |
| Validation and secret-free `PipelinePlan` | Yes |
| [ODCS](../03_DATA_CONTRACTS/ODCS.md) / [DTCS](../04_TRANSFORMATIONS/DTCS.md) / [DPCS](../05_PIPELINES/DPCS.md) interchange | Yes |
| Local in-process runtime + run reports | Yes |
| Observability providers + run history + event consumers | Yes (0.34 M6) |
| `etlantic report query` over durable history | Yes |
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
| CP1 identity / durable accept / SSE | Yes (foundation; CPn alone ≠ GA) |
| CP2 registry / isolation profiles | Yes (foundation) |
| CP3 durable work store + `/v1/durable/*` host routes | Yes (foundation; dual-write submit) |
| Multi-tenant durable orchestration GA | Yes — Supported profiles only (`isolated-deployment`, `dedicated-schema`); `shared-service` Experimental |
| Formal SLA / support response times | No |
| Production GUI | No — read-only-first operator console planned for 0.50 |
| Production multi-tenant GA | Yes — Supported profiles; see [support matrix](../11_DEVELOPMENT/cp_ga_support_matrix_0_43.json) |

## Security posture

- Plans never contain resolved secrets
- SQL plugins use structured compilation with identifier/parameter safety;
  untrusted raw SQL is out of scope
- Spark session credentials resolve at acquire time and never embed in plans
- Plugin allowlists / version pins are **available** via
  `Profile.plugin_allowlist` (production profiles fail closed when empty)
- **0.20–0.21 trust controls shipped:** SafeIoPolicy, pre-import allowlist +
  manifests, artifact/cache isolation keys, outbound default-deny,
  unsafe-serialization prohibition, versioned `SecurityEvent`, release digests /
  attestations (see [Release artifact verification](RELEASE_ARTIFACT_VERIFICATION.md))
  digests and GitHub attestations
- Report vulnerabilities privately; security fixes are supported on 0.44.x

### Shipped trust controls vs residual gaps

| Concern | Status |
|---|---|
| Secret-free plans/reports; `security_mode` | **Shipped** |
| Production plugin allowlist (selection, not sandbox) | **Shipped** |
| Safe I/O, outbound default-deny, serialization ban | **Shipped** |
| Artifact/cache isolation keys (single-tenant reference) | **Shipped** |
| Release SHA-256 manifest + GitHub attestations | **Release-gated** — verify the published assets with `gh attestation verify`; CycloneDX is optional, so confirm the SBOM or `sbom-warning.txt`. See [Release artifact verification](RELEASE_ARTIFACT_VERIFICATION.md). |
| Cross-tenant / multi-tenant isolation guarantees | **Available** for Supported profiles; `shared-service` Experimental; community non-SLA |
| Formal DoS capacity SLA | **Residual** (partial I/O budgets only) |
| Compliance-grade audit system of record | **Adopter-owned** (CLI reports are operational evidence) |
| HA/DR, SOC2/GDPR certs, identity/RBAC/SSO | **Adopter-owned / out of scope** |
| In-process multi-tenancy without Supported profile | **Out of scope** — use `isolated-deployment` / `dedicated-schema` |

Read [Security](../02_FOUNDATIONS/SECURITY.md) and the repository
[security policy](https://github.com/eddiethedean/etlantic/blob/main/SECURITY.md).
For the bounded reference topology and required controls, read
[Production Readiness](../06_EXECUTION/PRODUCTION_READINESS.md).

## Bounded production support (do not skip)

ETLantic **0.44.0** is a **Beta** (PyPI) release suitable for documented
single-tenant pilots and Supported multi-tenant profiles. Shipped trust
controls do not make an arbitrary shared-service topology safe.

The [Multi-Tenant Control Plane Plan](../11_DEVELOPMENT/MULTI_TENANT_CONTROL_PLANE_PLAN.md)
records the identity, isolation, persistence, durability, quota, audit, and
CP-GA graduation evidence for Supported profiles.

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
- AWS Secrets Manager / Vault (not shipped; optional provider packs planned for
  0.51); OS keyring **is** available via `etlantic-keyring`
- Process-local / durable file reports as an audit system of record
- Stable-foundation compatibility inventories (shipped in 0.37; Beta retained)
- Managed Databricks/EMR/Connect Spark providers (reference proof planned for
  0.47; supported packs planned for 0.51)
- **Undocumented advanced portable profiles** — Polars and PySpark ship the
  documented 0.17 Wave 1 / Wave 2 families; Pandas and SQL remain at kernel +
  `portable-relational/1`. Continuation profiles remain outside the advertised
  claim set. Keep a native
  `@implementation(...)` for profiles outside the advertised claim set, or
  for `portable_transform_policy="native"`.

## Enterprise readiness matrix

| Concern | Status in 0.44 |
|---|---|
| License | MIT (core and official plugins) |
| Supported versions / EOL | Current Beta line is 0.44.x; see [SECURITY.md](https://github.com/eddiethedean/etlantic/blob/main/SECURITY.md) |
| Compliance attestations (SOC2, GDPR cert) | Adopter-owned — not provided |
| Identity / RBAC / SSO | Out of scope — use process and network isolation |
| HA / DR / RPO / RTO | Adopter-owned topology |
| Release digests / provenance | Release workflow emits a SHA-256 manifest + GitHub attestations; CycloneDX is optional — verify the published assets using [Release artifact verification](RELEASE_ARTIFACT_VERIFICATION.md) |
| Audit system of record | Gap — durable/file reports are operational evidence only |
| Tested scale | Local/pilot workloads; no published capacity guarantees |
| Upgrade / rollback | Pin exact versions; see [Migration 0.41 → 0.42](../11_DEVELOPMENT/MIGRATION_0_41_TO_0_42.md) and [Upgrade hub](UPGRADE.md) |

## Recommended evaluation path

Follow this path **after** the green path (Install → Quickstart → First Pipeline
→ Engine selection), or as an enterprise diligence track:

1. [Installation](INSTALLATION.md) — `pip install etlantic==0.44.0`
2. [Quickstart](QUICKSTART.md) (`python -m etlantic init`; `examples/` requires a checkout)
3. [First Pipeline](FIRST_PIPELINE.md)
4. [Engine selection](ENGINE_SELECTION.md)
5. [Capabilities](CAPABILITIES.md)
6. Optional Gate A: checkout
   [`examples/interchange_polars_pandas.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/interchange_polars_pandas.py)
   with `etlantic-polars` + `etlantic-pandas` at `==0.44.0`
7. Optional engine examples from a checkout (portable kernels, SQL, PySpark,
   Airflow compile, Prefect)
8. [Migration 0.41 → 0.42](../11_DEVELOPMENT/MIGRATION_0_41_TO_0_42.md) if
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
