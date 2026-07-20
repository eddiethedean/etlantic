# Current Capabilities and Limitations

ETLantic **0.20.0** is **stable** for documented
single-tenant reference deployments. Experimental features remain
experimental, and multi-tenant isolation, deployment topology, compliance,
advanced multi-tenant control planes remain adopter-owned; 0.20 ships SBOM digests, attestations, and OIDC-preferred publish. This
page is the shortest answer to "What can I use today?"

## Recommended bounded production deployment

Use the documented reference envelope (see [Evaluator](EVALUATOR.md) and
[Production readiness](../06_EXECUTION/PRODUCTION_READINESS.md)):

1. Core + local/file storage ([Quickstart](QUICKSTART.md) paste, or checkout
   [`examples/quickstart.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/quickstart.py)
   / [`file_storage.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/file_storage.py))
2. Optional one engine: Polars **or** Pandas **or** SQL **or** local PySpark
3. Explicit production `Profile` JSON with `plugin_allowlist` (trim to engines you install)
4. CI `validate --format sarif` + reviewed `plan` JSON
5. No multi-tenant sharing of a process; no unresolved security Gaps from the
   [Security](../02_FOUNDATIONS/SECURITY.md) chapter

!!! note "Examples are not in the wheel"
    `pip install etlantic` does **not** install `examples/` or a ready-made
    `profiles/` tree. Use the paste-ready Quickstart, copy the profile JSON
    below, or clone the repository and run scripts with `uv run`.

## Available in 0.21

### Core authoring and validation

| Capability | Status |
|---|---|
| Typed data, transformation, and pipeline models | Available |
| `Extract` / `Load` / `asset=` authoring (`Source` / `Sink` removed) | Available |
| Structural and semantic validation | Available |
| ODCS, DTCS, and DPCS generation and loading | Available |
| Profiles and deterministic, secret-free pipeline plans | Available |
| `@Transformation.portable` / `etlantic.transform` → `dtcs.transform-plan/2` | Available |
| `Profile.portable_transform_policy` (`prefer` / `require` / `native`) | Available |
| DTCS 3.0 plan models / Rich Portable Analytics profiles | Available (install `dtcs>=0.13,<1`; normative content floor `dtcs` 0.14.0 where specs say so) |

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
| Portable Polars compiler (kernel + relational `/1`) | Available |
| Portable PySpark compiler (kernel + relational `/1`) | Available |
| Portable Pandas compiler (kernel + relational `/1`, eager) | Available |
| Portable SQL compiler (kernel + relational `/1`) | Available (`etlantic-sql`) |
| Advanced portable profiles (window, reshape, string-advanced, …) | Available on Polars + PySpark; Pandas/SQL remain baseline |
| Public portable transform conformance suite | Available |
| Versioned tabular interchange (`etlantic.interchange/1`) | **0.18.0 Gate A — Available** for Polars↔Pandas boundaries (still current in 0.21) |
| Best-effort Arrow-assisted conversion | Legacy helper; available when PyArrow is installed, but not the Gate A contract |
| Pre-import plugin authorization + static manifests | **Available in 0.21.0** |
| Unified SafeIoPolicy + artifact/cache isolation | **Available in 0.21.0** |
| Outbound SSRF policy + serialization bans | **Available in 0.21.0** |
| Release SBOM digests / attestations / OIDC publish | **Available in 0.21.0** |
| Contract and configuration freeze | **Available in 0.21.0** — deep plan immutability, fingerprint verify, `security_mode`, strict profiles |
| `etlantic-datafusion` | **Experimental** (Gate B) — stub package; not recommended |
| SQL protocol + PostgreSQL reference plugin | Available (`etlantic-sql`) |
| Spark protocol + local provider + native impl path | Available (`etlantic-pyspark`) |
| Lazy Spark region fusion (native path) | Available |
| Delta-compatible write intents | Available (fail-closed without Delta) |
| Airflow reference compiler | Available (`etlantic-airflow`) |
| Prefect direct-execution scheduler | Available (`etlantic-prefect`; local MVP) |

### Operations and security tooling

| Capability | Status |
|---|---|
| CLI compile / generate / diff / plugin / schema / reliability / viz | Available |
| Plugin allowlists and version pins | Available |
| SARIF diagnostics and file schema history | Available |
| File-backed report store and report compare | Available |
| Mermaid, Graphviz DOT, HTML lineage, JSON lineage | Available |
| IDE command/result JSON schemas | Available |
| Optional keyring / SQLModel / OpenTelemetry / SparkForge | Available |
| Agent guidance generators | Available |

### Experimental

| Capability | Status |
|---|---|
| Structured Streaming foundation | **Experimental** |

## Not included in 0.21

| Capability | Status |
|---|---|
| PySpark / SQL Arrow physical boundaries | Follow-up after Polars↔Pandas Gate A |
| `etlantic-datafusion` experimental engine | **Experimental in 0.21.0** (Gate B; not graduated) |
| `MERGE` / upsert in the reference SQL plugin | Not implemented (`sql_merge=False`; fail closed) |
| Managed Spark providers (Databricks/EMR/Connect) | Future / optional adapters |
| Event sensors / Dagster compilers | Future |
| Full LSP server productization | Continues in 1.5 |
| Registry-backed schema history | Continues in 1.2 |
| FastAPI control plane | Continues in 1.1 |
| Full SparkForge engine retirement inside SparkForge | Progressive path (see migration guide) |
| Stable 1.0 compatibility guarantees | Not yet |
| Portable continuation families (`relational-extended`, `temporal-iana`, …) | Not yet — see [Portable Compiler Matrix](../10_REFERENCE/PORTABLE_COMPILER_MATRIX.md) |
| Dedicated deployment / multi-worker ops guide | Partial — see [Ops Pilot](../06_EXECUTION/OPS_PILOT.md) |

## CI starter

Production profiles require a non-empty `Profile.plugin_allowlist` in an
explicit Profile JSON file (the built-in `production` name is empty and
fail-closed). Production fail-closed trust keys off
`security_mode="production"`, not the profile name or `security_domain`.
Never put secrets in plans, reports, or CI logs.

**Pip users:** create `profiles/prod.json` yourself (the package does not ship
this file). Start from the JSON below, then **trim `plugin_allowlist` to the
engines you actually install**.

**Checkout users:** you can also copy the docs companion:

```bash
mkdir -p profiles
cp docs/01_GETTING_STARTED/prod.example.json profiles/prod.json
# edit assets and trim allowlist for your pipeline
```

Starter profile (trim allowlist to one engine for first success):

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
    "local": null,
    "etlantic-polars": "==0.21.0"
  },
  "assets": {},
  "secrets": {},
  "secret_providers": {}
}
```

Full multi-engine allowlist companion (docs only):
[prod.example.json](prod.example.json).

Then validate and plan:

```bash
etlantic validate path/to/pipeline.py:MyPipeline --profile ./profiles/prod.json --format sarif
etlantic plan path/to/pipeline.py:MyPipeline --profile ./profiles/prod.json --format json
```

See [Production profiles](../06_EXECUTION/PRODUCTION_PROFILES.md),
[Runtime configuration](../10_REFERENCE/RUNTIME_CONFIGURATION.md),
[Ops Pilot](../06_EXECUTION/OPS_PILOT.md), and the
[Evaluator brief](EVALUATOR.md).

```bash
pip install 'etlantic==0.21.0'                 # core only — no engines
pip install 'etlantic-polars==0.21.0'          # Polars reference plugin
pip install 'etlantic-pandas==0.21.0'          # Pandas compatibility plugin
pip install 'etlantic-sql==0.21.0'             # PostgreSQL SQL reference plugin
pip install 'etlantic-pyspark==0.21.0'         # PySpark reference plugin
pip install 'etlantic-airflow==0.21.0'         # Airflow DAG compiler
pip install 'etlantic-prefect==0.21.0'         # Prefect direct-execution scheduler
pip install 'etlantic-keyring==0.21.0'         # OS keyring secret provider
pip install 'etlantic-sqlmodel==0.21.0'        # SQLModel contract bridge
pip install 'etlantic-sparkforge==0.21.0'      # SparkForge → ETLantic adapter
```

See [Installation](INSTALLATION.md) for verification and from-source contributor setup.

Core never imports Polars, Pandas, PyArrow, NumPy, database drivers, PySpark,
Airflow, SQLModel, keyring, OpenTelemetry, or SparkForge unless extras are
installed. Medallion bronze/silver/gold types are never part of core.

## Next Step

Continue diligence with the [Evaluator brief](EVALUATOR.md), pick an engine in
[Engine selection](ENGINE_SELECTION.md), or see [Storage today](../06_EXECUTION/STORAGE_TODAY.md)
for local persistence boundaries.
