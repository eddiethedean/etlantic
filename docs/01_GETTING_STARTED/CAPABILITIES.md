# Current Capabilities and Limitations

> **Status: Available in ETLantic 0.48.0 (shipped Beta).** What ships now for
> controlled single-tenant pilots and Supported multi-tenant profiles.

!!! tip "Adopter brief"
    Read **What works today** and **Limits** first. Residual gaps and CI
    starter JSON are further down for evaluators.

## What works today (0.48)

ETLantic 0.48.0 is a **Beta** release for documented, controlled,
single-tenant pilots (install `etlantic==0.48.0` from PyPI). You can embed an
HTTP control plane with **Supported** isolation profiles
(`isolated-deployment`, `dedicated-schema`). There is no hosted multi-tenant
SaaS and no SLA. It validates and
plans typed pipelines, runs them locally or through supported engine plugins,
compiles valid plans to supported orchestration targets, ships **human-governed
AI** context/proposal surfaces (`etlantic context` / `etlantic proposal`),
ships a **scheduler
and execution-host** (`etlantic schedule` / `scheduler serve` / `worker serve`),
developer intelligence (static analysis, `etlantic-lsp`, notebook surfaces),
keeps the advisory **planner and optimization SDK**, and keeps **Supported**
core streaming and bounded dynamic-control contracts. Kafka, Confluent registry,
Kubernetes, Spark Connect, and MCP extras are **Experimental**. `shared-service`
remains Experimental. Support is community **non-SLA**.

**Canonical first success:** [Quickstart](QUICKSTART.md)
(install `etlantic==0.48.0` from PyPI → `python -m etlantic init` → validate →
run). Do not start from repository `examples/` unless you have cloned the repo.
Headline 0.48/0.47 tutorials: [Human-governed AI](HUMAN_GOVERNED_AI.md) and
[Scheduler and worker](SCHEDULER_TUTORIAL.md).
Fit check: [Compare](COMPARE.md).

| Area | You can |
|---|---|
| Authoring | Typed `Data` / `Transformation` / `Pipeline`; builders; `PipelineDefinition` JSON; inspect/rewrite/provenance helpers |
| Validation | Wiring, contracts, capabilities, trust — before any write |
| Planning / optimization | Deterministic `PipelinePlan`; advisory `optimize_plan` / `etlantic plan optimize` with evidence, cost, proofs, and shadow compare |
| Engines | Local Python; Polars; Pandas; SQL (`etlantic-sql`); PySpark |
| Compile / schedule | Airflow DAG compile (`etlantic-airflow`); Prefect local MVP (`etlantic-prefect`); FastAPI-fronted schedules (`etlantic schedule`, `scheduler serve`, `worker serve`) |
| Agents | Bounded context bundles, proposal sandbox, `generate --kind agents`; apply via 0.42 approvals |
| Ops | SARIF/JSON diagnostics; secret-free plans; production `plugin_allowlist`, `optimization_pass_allowlist`, `schema_registry_allowlist`, and `resource_provider_allowlist` |
| Observability and evidence | Lifecycle correlation; observability providers; run-history providers; event consumers; `etlantic report query` |
| Testing | Application-pipeline cases via `etlantic.testing`; optimizer, streaming, and schedule-store conformance suites |
| Connectors | `etlantic.connectors` protocols; `local-files` Preview landing zone; Experimental `etlantic-s3` / `etlantic-kafka` / `etlantic-iceberg` / `etlantic-snowflake`; PostgreSQL via `etlantic-sql` |
| Resource / Spark extras | Experimental `etlantic-k8s` (`FakeKubernetes`) and `etlantic-spark-connect` (fake `SparkProvider`); live Kind/Databricks skipped |
| Streaming / dynamic control | Core `etlantic.streaming` types (Supported); Kafka/registry extras Experimental — never Available in core |
| Facades | `medallantic` medallion + SparkForge inventory/generate; optional `etlantic-keyring`, SQLModel, OTel |
| Developer intelligence | `etlantic.ide` + optional `etlantic[lsp]` / `etlantic[notebook]` (from 0.44) |
| Human-governed AI | `etlantic.agents` context bundles and proposal sandbox; `etlantic generate --kind agents`; Experimental `etlantic-mcp` |

## Limits

| Topic | ETLantic 0.48 |
|---|---|
| Maturity | Beta |
| Suitable for | Controlled single-tenant pilots; Supported multi-tenant profiles |
| Support | Community; no SLA |
| Not included | Formal enterprise SLA; `shared-service` production isolation; unbounded scale |

Experimental features remain experimental. Production multi-tenant is
**Available** only for Supported isolation profiles
(`isolated-deployment`, `dedicated-schema`); `shared-service` remains
Experimental. Pattern: community **non-SLA**. Roadmap programs live under
Contribute → Maintainers (see the
[multi-tenant control-plane plan](../11_DEVELOPMENT/MULTI_TENANT_CONTROL_PLANE_PLAN.md)).

## Supported standards policy (0.48)

For the 0.48 envelope, ETLantic supports these standards and
toolkits at the declared ranges (exact pins and protocol notes:
[Compatibility](../10_REFERENCE/COMPATIBILITY.md)):

| Standard / surface | 0.48 policy |
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

## Available in 0.48

### Human-governed AI

| Capability | Status |
|---|---|
| `etlantic.context_bundle/1` + `etlantic context bundle` | Available (`etlantic.agents`) |
| `etlantic.proposal/1` sandbox + `etlantic proposal validate` | Available; never applies files |
| `etlantic generate --kind agents` + user-region preservation | Available |
| Vendor-neutral `etlantic.ai_task/1` catalog | Available (Codex / Claude / Cursor adapters) |
| FastAPI `POST /v1/definitions/{id}/context` and `POST /v1/proposals/validate` | Available (`etlantic-fastapi`; compute only) |
| Approval handoff to `/v1/approvals*` | Available (reuse 0.42; no second mutation API) |
| Experimental `etlantic-mcp` `FakeMcpServer` | **Experimental** (live client skipped) |

### Scheduler/runner service and remote federation

| Capability | Status |
|---|---|
| `etlantic.schedule/1` + `etlantic.firing/1` + injectable clock | Available (`etlantic.control_plane`) |
| `ScheduleStore` + `MemoryScheduleStore` (tests/dev) | Available; production rejects memory (`PMSVC100`) |
| SQLModel schedules + migration `004_schedules_0_47` | Available (`etlantic-sqlmodel`) |
| Scheduler leader + due-timer loop (`etlantic scheduler serve`) | Available |
| Execution host (`etlantic worker serve`) wrapping CP3 | Available; no FastAPI import |
| FastAPI `/v1/schedules*` + definition schedules + health | Available (`etlantic-fastapi`; gateway only) |
| CLI `etlantic schedule create\|list\|inspect\|pause\|resume\|delete\|preview\|trigger` | Available |
| `etlantic.remote-runtime/1` fakes + placement reject-before-transfer | Available (in-process fake host) |
| `Profile.resource_provider_allowlist` (`PMRES140`) | Available |
| `etlantic.resource/1` + Experimental `etlantic-k8s` | **Experimental** (`FakeKubernetes`; live pack skipped) |
| Fake Spark Connect `SparkProvider` (`etlantic-spark-connect`) | **Experimental** (live pack skipped) |

## Previously shipped (control plane through 0.46)

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
| SQLModel CP4 snapshot stores + migration `003_cp4_governance` | Available (`etlantic-sqlmodel`; superseded head is `004_schedules_0_47`) |
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
| CLI compile / generate / diff / plugin / schema / reliability / erasure / viz / stream / schedule / scheduler / worker | Available |
| Observability providers (`etlantic.observability/1`) | Available |
| Run history providers (`etlantic.run_history/1`) | Available (file + in-memory reference) |
| Event consumers + `etlantic report query` | Available |
| Lifecycle event correlation (`etlantic.lifecycle_event/1`) | Available |
| Plugin allowlists and version pins | Available |
| SARIF diagnostics and file schema history | Available |
| File-backed report store and report compare | Available |
| Mermaid, Graphviz DOT, HTML lineage, JSON lineage | Available |
| IDE command/result JSON schemas | Available |
| No-import static workspace analysis + `etlantic watch` | Available |
| `etlantic-lsp` language server | Available |
| Notebook displays + `NotebookSession` | Available |
| Optional keyring / SQLModel / OpenTelemetry / SparkForge | Available |
| Agent guidance generators | Available |
| `medallantic` medallion facade | Available |

### Experimental

| Capability | Status |
|---|---|
| Structured Streaming foundation | **Experimental** |
| `etlantic-datafusion` | **Experimental** (Gate B stub — not recommended for pilots) |
| VS Code reference extension (`editors/vscode`) | **Experimental** |
| `etlantic-k8s` | **Experimental** (FakeKubernetes; live skip `047-K-01`) |
| `etlantic-spark-connect` | **Experimental** (fake SparkProvider; live skip `047-S-01`) |

See also [Experimental surfaces](EXPERIMENTAL_SURFACES.md).

## Planned and residual appendix (not unrestricted production)

| Capability | Status |
|---|---|
| Source/sink/storage connector SDK and reference set | **Available** in 0.38 — see [Connector SDK](../07_PLUGIN_SDK/CONNECTOR_SDK.md); cloud packages Experimental |
| Directory / CSV landing-zone connector (batch + incremental; continuous trigger in 0.39+) | **Available** (Preview) — [Landing zone](../06_EXECUTION/LANDING_ZONE.md) |
| OpenLineage metadata interoperability | **Experimental** outbound via `etlantic-openlineage` (non-authority; not production multi-tenant) |
| GitOps preview-to-production workflow | **Available** (CP-GA in-process evidence; see [WHATS_NEW_0_43](WHATS_NEW_0_43.md)) |
| PySpark / SQL Arrow physical boundaries | Follow-up after Polars↔Pandas Gate A |
| Managed Spark providers (Databricks/EMR/Connect) | Kubernetes Job + Spark Connect **Experimental fakes** ship in 0.47; live provider packs remain planned for 0.51 |
| FastAPI scheduler/runner service and remote federation | **Available in the bounded 0.47 envelope** — gateway routes plus separate scheduler/worker processes; see [What's new in 0.47](WHATS_NEW_0_47.md) and [ADR-023](../11_DEVELOPMENT/adr/ADR-023-SCHEDULER-SERVICE-AND-FEDERATION.md) |
| Human-governed AI context/proposals | **Available in the bounded 0.48 envelope** — redacted bundles, proposal sandbox, user-region generators; `etlantic-mcp` Experimental — see [What's new in 0.48](WHATS_NEW_0_48.md) and [ADR-024](../11_DEVELOPMENT/adr/ADR-024-HUMAN-GOVERNED-AI.md) |
| Bounded dynamic mapping/reduction and explicit conditional/failure/compensation branches | **Supported** (core) in 0.46 — [exit gate](../11_DEVELOPMENT/EXIT_GATE_0_46.md) / [ADR-022](../11_DEVELOPMENT/adr/ADR-022-DYNAMIC-CONTROL-AND-STREAMING.md) |
| Streaming poison-record/DLQ policy and schema-registry interoperability | **Supported** core policy/protocol in 0.46; Kafka (`etlantic-kafka`) and Confluent adapter (`etlantic-schemaregistry`) remain **Experimental** — never Available-in-core |
| Dagster / expanded Prefect / Argo compilers | Planned brownfield bridges in 0.49 |
| Read-only-first operator console | Planned first-class for 0.50 |
| AWS/Azure/GCP/Vault secret-provider packs | Planned as optional providers in 0.51 |
| TransformationModel incubation | Deferred to 0.52 |
| Full LSP server productization | **Available** in 0.44 (`etlantic-lsp`; VS Code client Experimental) |
| Registry-backed schema history | **Available** (CP2 metadata-only histories) |
| Production multi-tenant control plane | **Available** for Supported profiles (`isolated-deployment`, `dedicated-schema`); `shared-service` remains Experimental (see [support matrix](../11_DEVELOPMENT/cp_ga_support_matrix_0_43.json)) |
| Stable-foundation compatibility inventories | Available in 0.37 (surface / protocol / diagnostic tiers; Beta retained) |
| Portable continuation families (`relational-extended`, …) | Not yet — see [Portable Compiler Matrix](../10_REFERENCE/PORTABLE_COMPILER_MATRIX.md) |
| Dedicated multi-worker / multi-tenant ops control plane | Partial — Supported profiles via CP-GA; Operator Console remains 0.50 ([plan](../11_DEVELOPMENT/MULTI_TENANT_CONTROL_PLANE_PLAN.md)) |

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
(the sample uses Polars — install `etlantic-polars==0.48.0` first).

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
    "etlantic-polars": "==0.48.0"
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
pip install 'etlantic==0.48.0'
pip install 'etlantic[lsp]==0.48.0'            # optional language server
pip install 'etlantic-polars==0.48.0'          # optional
pip install 'etlantic-pandas==0.48.0'          # optional
pip install 'etlantic-sql==0.48.0'             # optional
pip install 'etlantic-pyspark==0.48.0'         # optional
pip install 'etlantic-airflow==0.48.0'         # optional
pip install 'etlantic-prefect==0.48.0'         # optional
pip install 'etlantic-keyring==0.48.0'         # optional
pip install 'etlantic-sqlmodel==0.48.0'        # optional
pip install 'medallantic==0.48.0'              # optional
```

See [Installation](INSTALLATION.md), [Evaluator brief](EVALUATOR.md), and
[Engine selection](ENGINE_SELECTION.md).
