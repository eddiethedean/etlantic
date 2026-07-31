# Current Capabilities and Limitations

> **Status: Available in ETLantic 0.36.0.** What ships now for controlled
> single-tenant pilots.

!!! tip "Adopter brief"
    Read **What works today** and **Limits** first. Residual gaps and CI
    starter JSON are further down for evaluators.

## What works today (0.36)

ETLantic 0.36.0 is a Beta release for documented, controlled,
single-tenant pilots. It validates and plans typed pipelines, runs them
locally or through supported engine plugins, and compiles valid plans to
supported orchestration targets.

**Canonical first success:** [Quickstart](QUICKSTART.md)
(install `etlantic==0.36.0` from PyPI → `python -m etlantic init` → validate →
run). Do not start from repository `examples/` unless you have cloned the repo.
Fit check: [Compare](COMPARE.md).

| Area | You can |
|---|---|
| Authoring | Typed `Data` / `Transformation` / `Pipeline`; builders; `PipelineDefinition` JSON; inspect/rewrite/provenance helpers |
| Validation | Wiring, contracts, capabilities, trust — before any write |
| Engines | Local Python; Polars; Pandas; SQL (`etlantic-sql`); PySpark |
| Compile / schedule | Airflow DAG compile (`etlantic-airflow`); Prefect local MVP (`etlantic-prefect`) |
| Ops | SARIF/JSON diagnostics; secret-free plans; production `plugin_allowlist` |
| Observability and evidence | Lifecycle correlation; observability providers; run-history providers; event consumers; `etlantic report query` |
| Testing (preview) | Application-pipeline cases via `etlantic.testing` |
| Facades | `medallantic` medallion + SparkForge inventory/generate; optional `etlantic-keyring`, SQLModel, OTel |

## Limits

| Topic | ETLantic 0.36 |
|---|---|
| Maturity | Beta |
| Suitable for | Controlled single-tenant pilots |
| Support | Community; no SLA |
| Not included | Managed multi-tenant control plane; unrestricted enterprise production |

Experimental features remain experimental. Multi-tenant isolation, deployment
topology, compliance, and advanced control planes remain adopter-owned in
0.36. Roadmap programs live under Contribute → Maintainers — not day-0 reading
(see the
[multi-tenant control-plane plan](../11_DEVELOPMENT/MULTI_TENANT_CONTROL_PLANE_PLAN.md)).

## Recommended bounded production deployment

1. Core + local/file storage via the [Quickstart](QUICKSTART.md)
2. Optional one engine: Polars **or** Pandas **or** SQL **or** local PySpark
3. Explicit production `Profile` JSON with `plugin_allowlist` (trim to engines you install)
4. CI `validate --format sarif` + reviewed `plan` JSON
5. No multi-tenant sharing of a process; see [Security](../02_FOUNDATIONS/SECURITY.md)

!!! note "Examples are not in the wheel"
    `pip install etlantic` does **not** install `examples/`. Use Quickstart
    paste paths. Checkout demos require a clone.

## Available in 0.36

### Migration and testing preview

| Capability | Status |
|---|---|
| `inspect_definition` / `rewrite_definition` / `definition_provenance` | Available |
| Application-pipeline testing (`PipelineTestCase`, snapshots, fakes) | Available (preview) |
| Medallantic SparkForge project inventory + safe native generation | Available (`medallantic`) |

## Previously shipped (through 0.34)

### Core authoring and validation

| Capability | Status |
|---|---|
| Typed data, transformation, and pipeline models | Available |
| Functional builders + `PipelineDefinition` | Available |
| `etlantic.pipeline/1` lossless JSON codecs | Available |
| Authoring catalog + immutable edit commands | Available |
| Service facade + optional FastAPI reference | Available (`etlantic-fastapi`) |
| `Extract` / `Load` / `asset=` authoring (`Source` / `Sink` removed) | Available |
| Structural and semantic validation (class or definition) | Available |
| [ODCS](../03_DATA_CONTRACTS/ODCS.md), [DTCS](../04_TRANSFORMATIONS/DTCS.md), and [DPCS](../05_PIPELINES/DPCS.md) generation and loading | Available |
| Profiles and deterministic, secret-free pipeline plans | Available |
| `@Transformation.portable` / `etlantic.transform` → `dtcs.transform-plan/2` | Available |
| `Profile.portable_transform_policy` (`prefer` / `require` / `native`) | Available |
| DTCS 3.0 plan models / Rich Portable Analytics profiles | Available (install `dtcs>=0.13,<1`; normative content floor `dtcs` 0.14.0 where specs say so) |
| Portable quality AST (`etlantic.quality/1`) + `make_quality_gate` | Available (provisional; `etl.quality`) |
| Quality plan fail-closed (`PMPLAN420` / `PMPLAN421`) | Available |
| Quality conformance suite (`run_quality_conformance_suite`) | Available |

### Local execution and storage

| Capability | Status |
|---|---|
| Local synchronous and asynchronous execution (`LocalScheduler`) | Available |
| Python transformation implementations | Available |
| Memory, callable, JSON, CSV, and no-write storage | Available |
| Run reports, structured logging, and local debugging | Available |
| Runtime secret references and env/file providers | Available |

### Optional engines and portable compilers

| Capability | Status |
|---|---|
| Dataframe protocol + Polars plugin (eager/lazy) | Available (`etlantic-polars`) |
| Pandas plugin (eager) | Available (`etlantic-pandas`) |
| Portable Polars / Pandas / SQL / PySpark compilers | Available |
| Advanced portable profiles (window, reshape, …) | Available on Polars + PySpark; Pandas/SQL remain baseline |
| Public portable transform conformance suite | Available |
| Versioned tabular interchange (`etlantic.interchange/1`) | **0.18.0 Gate A — Available** for Polars↔Pandas |
| Best-effort Arrow-assisted conversion | Legacy helper when PyArrow is installed (not the Gate A contract) |
| Pre-import plugin authorization + static manifests | Available |
| Unified SafeIoPolicy + artifact/cache isolation | Available |
| Outbound SSRF policy + serialization bans | Available |
| Runtime fault injection (test/dev) + terminal report semantics | Available |
| Microbenchmark baselines + CI regression gate | Available |
| Contract and configuration freeze | Available — fingerprint verify, `security_mode`, strict profiles |
| SQL protocol + PostgreSQL reference plugin | Available (`etlantic-sql`); PG `sql_merge=True`; SQLite fail-closed |
| Spark protocol + local provider | Available (`etlantic-pyspark`) |
| Delta-compatible write intents | Available (fail-closed without Delta) |
| Airflow reference compiler | Available (`etlantic-airflow`) |
| Prefect direct-execution scheduler | Available (`etlantic-prefect`; local MVP) |

### Operations and security tooling

| Capability | Status |
|---|---|
| CLI compile / generate / diff / plugin / schema / reliability / viz | Available |
| Observability providers (`etlantic.observability/1`) | Available |
| Run history providers (`etlantic.run_history/1`) | Available (file + in-memory reference) |
| Event consumers + `etlantic report query` | Available |
| Lifecycle event correlation (`etlantic.lifecycle_event/1`) | Available |
| Plugin allowlists and version pins | Available |
| SARIF diagnostics and file schema history | Available |
| File-backed report store and report compare | Available |
| Mermaid, Graphviz DOT, HTML lineage, JSON lineage | Available |
| IDE command/result JSON schemas | Available |
| Optional keyring / SQLModel / OpenTelemetry / SparkForge | Available |
| Agent guidance generators | Available |
| `medallantic` medallion facade | Available |

### Experimental

| Capability | Status |
|---|---|
| Structured Streaming foundation | **Experimental** |
| `etlantic-datafusion` | **Experimental** (Gate B stub — not recommended for pilots) |

See also [Experimental surfaces](EXPERIMENTAL_SURFACES.md).

## Planned and residual appendix (not unrestricted production)

| Capability | Status |
|---|---|
| Application-pipeline testing helpers | **Available (preview)** in 0.36 (`etlantic.testing`); graduation planned for 0.37 |
| Source/sink/storage connector SDK and reference set | Planned first-class for 0.38 |
| OpenLineage metadata interoperability | Planned as a tenant-aware 0.40 gate |
| GitOps preview-to-production workflow | Planned across 0.41–0.43 |
| PySpark / SQL Arrow physical boundaries | Follow-up after Polars↔Pandas Gate A |
| Managed Spark providers (Databricks/EMR/Connect) | Kubernetes/reference proof in 0.47; optional supported packs planned for 0.51 |
| Dagster / expanded Prefect / Argo compilers | Planned brownfield bridges in 0.49 |
| Read-only-first operator console | Planned first-class for 0.50 |
| AWS/Azure/GCP/Vault secret-provider packs | Planned as optional providers in 0.51 |
| TransformationModel incubation | Deferred to 0.52 |
| Full LSP server productization | Continues in 0.44 |
| Registry-backed schema history | Continues in 0.40 |
| Production multi-tenant control plane | **Planned first-class**: 0.39–0.42 incubation → 0.43 graduation (0.36 ships only the thin reference adapter) |
| Stable-foundation compatibility guarantees | Planned for 0.37 |
| Portable continuation families (`relational-extended`, …) | Not yet — see [Portable Compiler Matrix](../10_REFERENCE/PORTABLE_COMPILER_MATRIX.md) |
| Dedicated multi-worker / multi-tenant ops control plane | Not shipped; [first-class plan and hard gates](../11_DEVELOPMENT/MULTI_TENANT_CONTROL_PLANE_PLAN.md) |

**Already shipped (0.28–0.34):** Plugin SDK `/1` freeze; quality; materialization;
PySpark/Delta parity; SQL builder parity; M6 observability, run history, and
production conformance. See
[What's New in 0.34](WHATS_NEW_0_34.md).

## CI starter

Production profiles require a non-empty `Profile.plugin_allowlist` in an
explicit Profile JSON file (the built-in `production` name is empty and
fail-closed). Production fail-closed trust keys off
`security_mode="production"`, not the profile name or `security_domain`.
Never put secrets in plans, reports, or CI logs.

**Pip users:** create `profiles/prod.json` yourself. Start from the JSON
below, then **trim `plugin_allowlist` to the engines you actually install**
(the sample uses Polars — install `etlantic-polars==0.36.0` first).

```json
{
  "name": "prod-example",
  "security_mode": "production",
  "security_domain": "production",
  "orchestrator": "local",
  "dataframe_engine": "polars",
  "portable_transform_policy": "require",
  "validation_policy": "strict",
  "allow_trusted_sql": false,
  "plugin_allowlist": {
    "etlantic-polars": "==0.36.0"
  },
  "assets": {},
  "secrets": {},
  "secret_providers": {}
}
```

Full multi-engine companion: [prod.example.json](prod.example.json).

```bash
python -m etlantic validate path/to/pipeline.py:MyPipeline --profile ./profiles/prod.json --format sarif
python -m etlantic plan path/to/pipeline.py:MyPipeline --profile ./profiles/prod.json --format json
```

```bash
pip install 'etlantic==0.36.0'
pip install 'etlantic-polars==0.36.0'          # optional
pip install 'etlantic-pandas==0.36.0'          # optional
pip install 'etlantic-sql==0.36.0'             # optional
pip install 'etlantic-pyspark==0.36.0'         # optional
pip install 'etlantic-airflow==0.36.0'         # optional
pip install 'etlantic-prefect==0.36.0'         # optional
pip install 'etlantic-keyring==0.36.0'         # optional
pip install 'etlantic-sqlmodel==0.36.0'        # optional
pip install 'medallantic==0.36.0'              # optional
```

See [Installation](INSTALLATION.md), [Evaluator brief](EVALUATOR.md), and
[Engine selection](ENGINE_SELECTION.md).
