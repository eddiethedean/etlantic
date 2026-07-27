# Enterprise Evaluation Guide

> **Status: Available in ETLantic 0.25.0.** A consolidated diligence packet for
> technical evaluators and enterprise decision-makers.

## Residual evaluation lead

| Topic | 0.25 |
|---|---|
| Maturity | **Beta** (PyPI) |
| Suitable for | Documented single-tenant pilots |
| Not suitable for | Unrestricted enterprise production / multi-tenant control planes |
| Support | Community; **no formal SLA** |
| LTS / support window | Current published minor (`0.25.x`) only |
| Compliance / SoR | Adopter-owned beyond shipped SBOM digests and GitHub attestations |

ETLantic is a typed, contract-driven **pipeline framework** for Python. You
define datasets, transformations, and pipelines once; ETLantic validates and
plans them; optional plugins execute on Polars, Pandas, SQL, PySpark, Airflow
(compile), and Prefect (local MVP).

ETLantic is **not** a dataframe engine, distributed scheduler, warehouse, secret
manager, or compliance audit system of record.

Start with the one-page [Evaluator Brief](EVALUATOR.md) for a capability
matrix. Use this guide to assemble a complete evaluation packet.

## Evaluation checklist

### 1. Understand the support boundary

| Document | Purpose |
|---|---|
| [Capabilities](CAPABILITIES.md) | Shipped vs experimental vs future |
| [Production readiness](../06_EXECUTION/PRODUCTION_READINESS.md) | Reference topology, required controls, honest gaps |
| [Compare](COMPARE.md) | Positioning vs dbt, Airflow, Pandera, and peers |
| [Support](../11_DEVELOPMENT/SUPPORT.md) | Community support scope and explicit non-goals |

### 2. Run the green path

1. [Installation](INSTALLATION.md) — `pip install etlantic==0.25.0`
2. [Quickstart](QUICKSTART.md) — `etlantic init`, validate, plan, run
3. [First Pipeline](FIRST_PIPELINE.md) — evolve the generated project
4. [Engine selection](ENGINE_SELECTION.md) — pick one engine tutorial

### 3. Security and trust review

| Document | Purpose |
|---|---|
| [Security](../02_FOUNDATIONS/SECURITY.md) | Threat model, trust boundaries, verification checklist |
| [Repository SECURITY.md](https://github.com/eddiethedean/etlantic/blob/main/SECURITY.md) | Supported versions, private reporting, disclosure targets |
| [Production profiles](../06_EXECUTION/PRODUCTION_PROFILES.md) | Fail-closed `production` template and allowlist behavior |
| [Secrets management](../06_EXECUTION/SECRETS_MANAGEMENT.md) | Shipped secret providers and future cloud managers |

Key facts for evaluators:

- Plans and compiled artifacts are **secret-free** by design.
- Production profiles require a non-empty `plugin_allowlist` and fail closed.
- Plugin allowlists are **selection**, not sandboxing—use process isolation.
- Release CI emits SPDX SBOM digests and GitHub build provenance attestations.

### 4. Operations and deployment review

| Document | Purpose |
|---|---|
| [Deployment](../06_EXECUTION/DEPLOYMENT.md) | Process model, profile locking, adopter ownership |
| [CI integration](../06_EXECUTION/CI_INTEGRATION.md) | SARIF gates, production-profile validation pattern |
| [Pilot walkthrough](../06_EXECUTION/PILOT_WALKTHROUGH.md) | Controlled evaluation from install through production profile |
| [Ops pilot](../06_EXECUTION/OPS_PILOT.md) | Pin matrix, failure ownership, Airflow handoff |
| [Ops examples](OPS_EXAMPLES.md) | Secrets, schema, SARIF snippets for CI |

Copy [prod.example.json](prod.example.json) into your own `profiles/prod.json`
and fill `assets` for your pipeline bindings before production-profile testing.

### 5. Supply chain and versioning

| Artifact | Location |
|---|---|
| Version pins | Pin `etlantic==0.25.0` and matching plugin minors |
| Changelog | [CHANGELOG](../CHANGELOG.md) |
| Upgrade path | [Upgrade hub](UPGRADE.md), [Migration 0.24 → 0.25](../11_DEVELOPMENT/MIGRATION_0_24_TO_0_25.md) |
| API stability | [Deprecation policy](../11_DEVELOPMENT/DEPRECATION_POLICY.md), [Surface inventory](../10_REFERENCE/SURFACE_INVENTORY.md) |
| Known limitations | [Known issues](../10_REFERENCE/KNOWN_ISSUES.md) |

### 6. Optional deep dives

| Goal | Guide |
|---|---|
| Gate A Polars↔Pandas interchange | [Interchange example](../09_EXAMPLES/INTERCHANGE_POLARS_PANDAS.md) |
| Portable transforms | [Portable transformations](../04_TRANSFORMATIONS/PORTABLE_TRANSFORMATIONS.md) |
| Plugin SDK evaluation | [Building a Plugin](../07_PLUGIN_SDK/BUILDING_A_PLUGIN.md) |
| Resilience / performance budgets | [Exit gate 0.23](../11_DEVELOPMENT/EXIT_GATE_0_23.md) |
| Programmatic authoring / JSON | [Exit gate 0.24](../11_DEVELOPMENT/EXIT_GATE_0_24.md) |

## Explicit non-goals (do not expect these from docs or product)

- Multi-tenant isolation guarantees or a managed control plane
- SOC2, GDPR, HIPAA, or other compliance attestations
- HA/DR runbooks, Kubernetes reference architectures, or capacity SLAs
- Cloud secret managers (Vault, AWS Secrets Manager)—OS keyring ships via
  `etlantic-keyring`
- Formal support SLAs or guaranteed response times

## Decision summary

**Adopt ETLantic when** you need a typed control layer for single-tenant Python
pipelines, secret-free plans, SARIF-friendly CI validation, and honest plugin
boundaries—and you own deployment topology, compliance, and operational runbooks.

**Defer or supplement when** you require multi-tenant SaaS, enterprise compliance
certifications, or a turnkey managed runtime without adopter-owned ops.

## Next steps

- Practitioners: continue the [Current 0.25 Guide](CURRENT_VERSION.md)
- Decision-makers: return to [Evaluator Brief](EVALUATOR.md) with this checklist
- Production pilots: [Pilot walkthrough](../06_EXECUTION/PILOT_WALKTHROUGH.md)
