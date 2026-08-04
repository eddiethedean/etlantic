# Current Capabilities and Limitations

> **Status: Available in ETLantic 0.42.0.** What ships now for controlled
> single-tenant pilots.

!!! tip "Adopter brief"
    Read **What works today** and **Limits** first. Residual gaps and CI
    starter JSON are further down for evaluators.

## What works today (0.42)

ETLantic 0.42.0 is a Beta release for documented, controlled,
single-tenant pilots. It validates and plans typed pipelines, runs them
locally or through supported engine plugins, and compiles valid plans to
supported orchestration targets.

**Canonical first success:** [Quickstart](QUICKSTART.md)
(install `etlantic==0.42.0` from PyPI → `python -m etlantic init` → validate →
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
| Testing | Application-pipeline cases via `etlantic.testing` (stable foundation) |
| Connectors | `etlantic.connectors` protocols; `local-files` Preview landing zone; Experimental `etlantic-s3` / `etlantic-iceberg` / `etlantic-snowflake`; PostgreSQL via `etlantic-sql` |
| Facades | `medallantic` medallion + SparkForge inventory/generate; optional `etlantic-keyring`, SQLModel, OTel |

## Limits

| Topic | ETLantic 0.40 |
|---|---|
| Maturity | Beta |
| Suitable for | Controlled single-tenant pilots |
| Support | Community; no SLA |
| Not included | Managed multi-tenant control plane; unrestricted enterprise production |

Experimental features remain experimental. Multi-tenant isolation, deployment
topology, compliance, and advanced control planes remain adopter-owned in
0.40 (CP2 is incubated; production isolation remains **0.43**). Roadmap
programs live under Contribute → Maintainers — not day-0 reading (see the
[multi-tenant control-plane plan](../11_DEVELOPMENT/MULTI_TENANT_CONTROL_PLANE_PLAN.md)).

## Supported standards policy (0.40)

For the 0.40 foundation envelope, ETLantic supports these standards and
toolkits at the declared ranges (exact pins and protocol notes:
[Compatibility](../10_REFERENCE/COMPATIBILITY.md)):

| Standard / surface | 0.40 foundation policy |
|---|---|
| Python | 3.11, 3.12, 3.13 (`requires-python >=3.11`) |
| ContractModel | `>=0.2,<0.3` ([ODCS](../03_DATA_CONTRACTS/ODCS.md) `v3.1.0` document model) |
| [ODCS](../03_DATA_CONTRACTS/ODCS.md) | Generate / load via ContractModel / `Data` paths |
| [DTCS](../04_TRANSFORMATIONS/DTCS.md) | Spec `3.0.0` (`dtcsVersion: "3.0.0"`); toolkit `dtcs>=0.13,<1` (2.0.0 / 1.0.0 remain readable) |
| [DPCS](../05_PIPELINES/DPCS.md) | Toolkit `dpcs>=0.13,<1` |

Outside these ranges, expect fail-closed unknown-version / migration
diagnostics—not silent acceptance. Diagnostic **code family** stability:
[Diagnostic-code stability tiers](../10_REFERENCE/DIAGNOSTIC_STABILITY_TIERS.md).
Public surface classes:
[Surface inventory](../10_REFERENCE/SURFACE_INVENTORY.md).

## Recommended bounded production deployment

1. Core + local/file storage via the [Quickstart](QUICKSTART.md)
2. Optional one engine: Polars **or** Pandas **or** SQL **or** local PySpark
3. Explicit production `Profile` JSON with `plugin_allowlist` (trim to engines you install)
4. CI `validate --format sarif` + reviewed `plan` JSON
5. No multi-tenant sharing of a process; see [Security](../02_FOUNDATIONS/SECURITY.md)

!!! note "Examples are not in the wheel"
    `pip install etlantic` does **not** install `examples/`. Use Quickstart
    paste paths. Checkout demos require a clone.

## Available in 0.42

### Control-plane policy, quotas, and audit (CP4)

| Capability | Status |
|---|---|
| `PolicyProvider` + `MemoryPolicyProvider` + gates | Available (`etlantic.control_plane`) |
| Approvals / SoD + quota admission / suspension | Available |
| Delivery objectives + notification routing | Available |
| Governed erasure (request → plan → execute → report) | Available; CLI `etlantic erasure` |
| Attestations + signed schema observations | Available |
| `AuditEvidenceStore` hash chain | Available |
| FastAPI `/v1/policy|approvals|quotas|erasure|audit|attestations|objectives` | Available (`etlantic-fastapi`) |
| SQLModel CP4 snapshot stores + migration `003_cp4_governance` | Available (`etlantic-sqlmodel`) |
| CP4 conformance + outage matrix evidence | Available (`etlantic.testing` / `check_cp4_chaos.py`) |

### Control-plane durable work (CP3)

| Capability | Status |
|---|---|
| `DurableWorkStore` + `MemoryDurableWorkStore` | Available (`etlantic.control_plane`) |
| SQLModel durable reference provider + migration `002_durable_cp3` | Available (`etlantic-sqlmodel`) |
| FastAPI `/v1/durable/*` + optional submit dual-write | Available (`etlantic-fastapi`) |
| Leases / fencing / heartbeat / release | Available |
| Checkpoint CAS, replay, repair/backfill plans, preview TTL | Available |
| Effects / diagnose / shadow HTTP routes | Available |
| Durable-work conformance + chaos evidence | Available (`etlantic.testing`) |

### Migration and testing foundation

| Capability | Status |
|---|---|
| `inspect_definition` / `rewrite_definition` / `definition_provenance` | Available |
| Application-pipeline testing (`PipelineTestCase`, snapshots, fakes) | Available (stable foundation) |
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
| Plan immutability helpers | Available — nest `deep_freeze` + canonical serialize + fingerprint verify (not full object-graph freeze) |
| Diagnostic-code stability tiers | Available — [tiers](../10_REFERENCE/DIAGNOSTIC_STABILITY_TIERS.md) |
| SQL protocol + PostgreSQL reference plugin | Available (`etlantic-sql`); PG `sql_merge=True`; SQLite fail-closed |
| Spark protocol + local provider | Available (`etlantic-pyspark`) |
| Delta-compatible write intents | Available (fail-closed without Delta) |
| Airflow reference compiler | Available (`etlantic-airflow`) |
| Prefect direct-execution scheduler | Available (`etlantic-prefect`; local MVP) |

### Operations and security tooling

| Capability | Status |
|---|---|
| CLI compile / generate / diff / plugin / schema / reliability / erasure / viz | Available |
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
| Source/sink/storage connector SDK and reference set | **Available** in 0.38 — see [Connector SDK](../07_PLUGIN_SDK/CONNECTOR_SDK.md); cloud packages Experimental |
| Directory / CSV landing-zone connector (batch + incremental; continuous trigger in 0.39+) | **Available** (Preview) — [Landing zone](../06_EXECUTION/LANDING_ZONE.md) |
| OpenLineage metadata interoperability | **Experimental** outbound via `etlantic-openlineage` (non-authority; not production multi-tenant) |
| GitOps preview-to-production workflow | Planned across 0.41–0.43 |
| PySpark / SQL Arrow physical boundaries | Follow-up after Polars↔Pandas Gate A |
| Managed Spark providers (Databricks/EMR/Connect) | Kubernetes/reference proof in 0.47; optional supported packs planned for 0.51 |
| Bounded dynamic mapping/reduction and explicit conditional/failure/compensation branches | Planned first-class for 0.46 |
| Streaming poison-record/DLQ policy and schema-registry interoperability | Planned first-class for 0.46 |
| Dagster / expanded Prefect / Argo compilers | Planned brownfield bridges in 0.49 |
| Read-only-first operator console | Planned first-class for 0.50 |
| AWS/Azure/GCP/Vault secret-provider packs | Planned as optional providers in 0.51 |
| TransformationModel incubation | Deferred to 0.52 |
| Full LSP server productization | Continues in 0.44 |
| Registry-backed schema history | **Available** (CP2 metadata-only histories) |
| Production multi-tenant control plane | **Planned first-class**: CP1 in 0.39 → CP2 incubated in 0.40 → 0.41–0.42 continue → **0.43** graduation (CP2 ≠ production multi-tenant isolation) |
| Stable-foundation compatibility inventories | Available in 0.37 (surface / protocol / diagnostic tiers; Beta retained) |
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
(the sample uses Polars — install `etlantic-polars==0.42.0` first).

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
    "etlantic-polars": "==0.42.0"
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
pip install 'etlantic==0.42.0'
pip install 'etlantic-polars==0.42.0'          # optional
pip install 'etlantic-pandas==0.42.0'          # optional
pip install 'etlantic-sql==0.42.0'             # optional
pip install 'etlantic-pyspark==0.42.0'         # optional
pip install 'etlantic-airflow==0.42.0'         # optional
pip install 'etlantic-prefect==0.42.0'         # optional
pip install 'etlantic-keyring==0.42.0'         # optional
pip install 'etlantic-sqlmodel==0.42.0'        # optional
pip install 'medallantic==0.42.0'              # optional
```

See [Installation](INSTALLATION.md), [Evaluator brief](EVALUATOR.md), and
[Engine selection](ENGINE_SELECTION.md).
