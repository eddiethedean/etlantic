# Dependency Strategy

This document records the recommended third-party packages for Pipelantic,
where they should be used, and which architectural boundaries they must not
cross.

The recommendations are based on project maturity, maintenance activity,
typing and API quality, security posture, dependency weight, ecosystem
adoption, and fit with Pipelantic's public design.

Versions must be selected and locked when implementation begins. The ranges in
this document describe compatibility intent, not final pins.

## Policy

Pipelantic should prefer:

1. the Python standard library when it provides a sufficient stable API;
2. a small hard-dependency set for behavior central to every installation;
3. extras for user-facing capabilities that are optional but maintained in the
   main distribution;
4. separate plugin distributions for heavy or backend-specific integrations;
5. development-only tools that never leak into runtime imports.

Every dependency must have:

- a named owner inside the project;
- a documented reason for use;
- an allowed import boundary;
- a compatible-version range;
- lockfile coverage and vulnerability scanning;
- a removal or replacement strategy.

## Recommended Hard Dependencies

The base installation should remain intentionally small.

| Package | Purpose | Recommendation |
|---|---|---|
| `contractmodel` | Operational data-contract API | Hard dependency once its integration API is stable |
| `pydantic` | Typed authoring, validation, serialization, JSON Schema | Hard dependency |
| `anyio` | Structured concurrency, cancellation, task groups, thread bridges | Hard dependency for the local runtime |
| `packaging` | PEP-compliant versions, requirements, and specifier checks | Hard dependency |
| `typing-extensions` | Selected newer typing primitives on supported Python versions | Conditional hard dependency |

### ContractModel

Pipelantic should depend on ContractModel's public data-contract interfaces
rather than duplicating its Pydantic and ODCS operational behavior.

This dependency must remain one-directional:

```text
ContractModel
      ▲
      │
Pipelantic
```

ContractModel must never import Pipelantic.

If ContractModel's public integration surface is not stable when Pipelantic
implementation begins, isolate it behind a small internal adapter until it is.

### Pydantic

Pydantic is justified as a hard dependency because Pipelantic's documented
authoring experience already treats Python types as the modeling language.
Pydantic provides production-grade type-driven validation, serialization, and
JSON Schema generation.

Use Pydantic for:

- public configuration and result models;
- contract-compatible authoring models;
- discriminated unions;
- input validation at API boundaries;
- stable JSON serialization;
- schema generation.

Do not use Pydantic models as mutable runtime state containers. Prefer frozen
models or standard-library dataclasses for immutable internal graph and plan
objects when that produces clearer semantics.

Pipelantic should target Pydantic v2 only and define a tested minor-version
window rather than relying on unbounded upgrades. Pydantic describes itself as
production-stable and continues to publish active v2 releases.

### AnyIO

AnyIO is a strong match for the reference runtime because it supplies:

- structured task groups;
- cancellation scopes and timeouts;
- capacity limiters;
- synchronization primitives;
- worker-thread and worker-process bridges;
- context propagation;
- pytest integration.

The runtime should expose Pipelantic semantics, not AnyIO objects. AnyIO is
an implementation dependency behind runtime protocols.

AnyIO also keeps the runtime compatible with asyncio while avoiding hand-built
task and cancellation management. Pipelantic does not need to promise Trio
support merely because AnyIO can provide it; backend support should be tested
and declared explicitly.

### Packaging

Use PyPA's `packaging` library for:

- plugin version constraints;
- core and SDK compatibility ranges;
- supported standard-version ranges;
- normalized version comparison;
- requirement and marker evaluation.

Do not implement version parsing or compare version strings manually.

### Typing Extensions

Use `typing-extensions` only for features that materially improve the public
typing API on the minimum supported Python version. Re-evaluate it whenever the
minimum Python version changes.

## Standard Library First

The following needs do not justify another hard dependency initially:

| Need | Standard-library choice |
|---|---|
| Plugin metadata and entry points | `importlib.metadata` |
| Package resources | `importlib.resources` |
| DAG topological sorting | `graphlib.TopologicalSorter` plus owned graph utilities |
| Lifespan composition | `contextlib.AsyncExitStack` |
| Context propagation | `contextvars` |
| TOML loading | `tomllib` |
| JSON | `json` |
| Logging facade | `logging` |
| Immutable records | frozen `dataclasses` |
| Hashing | `hashlib` |
| URLs and paths | `urllib.parse` and `pathlib` |

`importlib.metadata` exposes distribution metadata and entry points without
requiring `pkg_resources`. Discovery should inspect entry-point metadata first
and call `EntryPoint.load()` only after trust policy permits the import.

## Recommended Extras

Extras belong in the main distribution when they are lightweight integrations
maintained as part of Pipelantic but are not required by every user.

### `pipelantic[yaml]`

Recommended package:

- `ruamel.yaml`

Reasons:

- YAML 1.2 support;
- round-trip preservation of comments, ordering, anchors, and formatting;
- source-aware editing workflows;
- configurable maximum nesting depth in current releases.

Requirements:

- never use `typ="unsafe"`;
- prohibit Python object constructors;
- set depth, size, alias, and document-count limits;
- pin a tested minor range because the project has evolved its APIs;
- keep JSON and TOML usable without this extra.

If Pipelantic only needed one-way YAML decoding, PyYAML would be smaller.
The planned source-preserving diagnostics, migration, and formatting workflows
make `ruamel.yaml` the better fit.

### `pipelantic[jsonschema]`

Recommended packages:

- `jsonschema`
- `referencing`

Use these for standards-facing JSON Schema validation and explicit reference
registries. `jsonschema` supports current and historical JSON Schema drafts,
lazy enumeration of validation errors, and structured error paths.

Do not enable network retrieval implicitly. Pipelantic must provide its own
bounded resolver policy and pass approved resources into `referencing`.

Pydantic remains the Python model validator; `jsonschema` validates portable
schema artifacts. They solve different problems.

### `pipelantic[cli]`

Recommended packages:

- `cyclopts`
- `rich`

Cyclopts fits Pipelantic's type-driven philosophy, supports typed function
and class parameters, shell completion, and generated CLI documentation. Rich
provides readable diagnostic tables, trees, progress, and tracebacks.

The CLI must remain a thin adapter over the public Python API. Core modules
must not import Cyclopts or Rich.

Security requirements:

- disable local-variable display in production tracebacks;
- escape untrusted Rich markup;
- preserve plain-text and JSON output modes;
- never make color or terminal detection part of result semantics.

### `pipelantic[http]`

Recommended package:

- `httpx`

Use HTTPX for explicitly enabled remote references, callbacks, webhooks, and
remote providers because it offers synchronous and asynchronous clients with a
consistent API.

All use must pass through Pipelantic network policy:

- destination allowlists;
- DNS and redirect validation;
- timeouts and response-size limits;
- TLS verification;
- proxy policy;
- blocked link-local, loopback, metadata, and private destinations by default.

### `pipelantic[docs]`

Recommended packages:

- `jinja2`
- `markdown-it-py`
- `markupsafe`
- `graphviz`

Use Jinja and MarkupSafe for generated HTML templates, `markdown-it-py` for
controlled Markdown rendering, and the Python `graphviz` package for DOT
construction.

The Graphviz system executable remains an external tool. Mermaid output needs
no Python runtime dependency.

Templates and labels must be escaped. Graphviz and documentation subprocesses
must receive argument lists, never shell strings.

### `pipelantic[observability]`

Recommended packages:

- `opentelemetry-api`
- optionally `structlog`

A library should depend only on the OpenTelemetry API when emitting spans and
metrics. Applications or deployment plugins install and configure
`opentelemetry-sdk` and exporters.

OpenTelemetry currently marks Python traces and metrics stable while its log
signal remains less mature. Pipelantic should therefore keep standard
Python logging canonical and bridge it to OpenTelemetry through a provider.

`structlog` is a good optional provider for structured event processing, but it
should not become the logging facade required by every plugin. Plugins log
through Pipelantic's context or standard `logging`.

### `pipelantic[notebook]`

Recommended packages:

- `ipython`
- `ipywidgets`

IPython supplies the rich display protocol needed to render pipelines, plans,
diagnostics, lineage, artifacts, and reports in notebooks without changing
their underlying public models. Ipywidgets may provide optional progress,
selection, cancellation, and report-navigation controls.

Pipelantic should not depend on the complete Jupyter distribution. JupyterLab,
Notebook, VS Code notebooks, and other frontends should consume the same
IPython display objects and public execution APIs.

Notebook integration requirements:

- rich representations must be side-effect free;
- rendering must not resolve secrets, import execution plugins, access
  artifacts, or perform network requests implicitly;
- dataframe and artifact previews must enforce row, column, byte, and rendering
  limits;
- widget actions must create ordinary `RunRequest` values and consume ordinary
  lifecycle events and reports;
- notebook helpers must expose active profiles, overrides, selections, and
  stale model state explicitly;
- every rich object must retain a useful plain-text representation;
- widgets must be an enhancement, not a requirement for notebook use.

Use `nbformat` and `nbclient` as development or documentation dependencies when
the project begins executing example notebooks in CI. They should not be
runtime dependencies of the notebook extra.

### AI coding assistants

Pipelantic should generate documentation-only instruction and skill artifacts
for Codex, Claude Code, and Cursor without depending on their model SDKs.
Repository guidance and task workflows should be generated from one canonical,
vendor-neutral catalog rather than maintained as divergent prompts.

The existing template and serialization facilities may generate `AGENTS.md`,
`CLAUDE.md`, Codex `SKILL.md` packages, scoped Cursor rules and commands, and
bounded machine-readable context bundles. Vendor SDKs, hosted-agent clients,
and model APIs belong only in separately distributed adapters with their own
authentication, network, retention, and security policies.

An optional read-only MCP server should evaluate the official MCP Python SDK
when implementation begins. It must expose Pipelantic's public inspection APIs
rather than creating a second internal API.

## Separate Plugin Dependencies

Heavy backends and infrastructure libraries belong in separately installable
plugin distributions.

### Dataframe and interchange plugins

| Distribution concept | Dependencies |
|---|---|
| `pipelantic-polars` | `polars`, optional `pyarrow` |
| `pipelantic-pandas` | `pandas`, optional `pyarrow` |
| Shared Arrow interchange extra | `pyarrow` |

Polars should remain the reference dataframe backend. Pandas should remain a
fully supported compatibility backend. Neither is imported by Pipelantic
core.

PyArrow is valuable for cross-backend tabular interchange and Parquet, but its
binary size makes it unsuitable as a core dependency.

### SQL plugins

Recommended packages:

- `sqlalchemy` in the general SQL plugin;
- database drivers in dialect-specific extras or provider packages;
- optionally `sqlglot` for SQL parsing, normalization, lineage analysis, or
  dialect translation after a focused evaluation.

SQLAlchemy Core is mature and provides composable SQL expressions, bind
parameters, dialect compilation, connections, and transactions without
requiring its ORM.

Pipelantic should not expose SQLAlchemy classes from core protocols. A SQL
plugin may accept or adapt them.

Do not add SQLGlot merely because it is powerful. Adopt it only if
Pipelantic needs to parse user SQL or perform cross-dialect AST analysis
that SQLAlchemy does not provide. Query optimization remains database-owned
unless Pipelantic can prove semantic preservation.

### Storage plugins

Recommended foundation:

- `fsspec`

Fsspec provides a uniform file-like interface across local, remote, and
embedded filesystems and has no dependencies in its base installation.

Use it inside storage plugins, not core. Individual protocols should remain
separate dependencies:

- `s3fs` for S3;
- `gcsfs` for Google Cloud Storage;
- `adlfs` for Azure;
- provider SDKs only where their capabilities are required.

Pipelantic security policy must still govern schemes, destinations,
credentials, and path access. Fsspec is an interface, not a security boundary.

### Retry execution

Recommended package:

- `tenacity`, inside providers or the local runtime implementation

Tenacity supplies synchronous and asynchronous retry controllers, bounded stop
conditions, waits, predicates, and callbacks.

Do not expose Tenacity policies as Pipelantic's public retry model. Translate
portable `RetryPolicy` values into Tenacity internally. Never use Tenacity's
unbounded default retry behavior.

External orchestrators should normally compile retry intent into their native
retry mechanism rather than run Tenacity inside a task.

### Spark plugins

| Plugin | Dependencies |
|---|---|
| PySpark execution | `pyspark` |
| Delta Lake support | `delta-spark` where appropriate |
| Databricks provider | official Databricks SDK or connector selected by capability |

These packages must never be extras on the core wheel if that would cause
ordinary installations to resolve or download them.

### Orchestrator plugins

Airflow, Dagster, Prefect, Argo, and future integrations each belong in their
own distribution. Their SDKs and providers are dependencies of those
distributions only.

### FastAPI integration

The post-1.0 control API belongs in a separate `pipelantic-fastapi`
distribution.

Recommended dependencies:

- `fastapi` for typed HTTP APIs, OpenAPI 3.1, dependencies, lifespan, and
  WebSockets;
- Pipelantic core for plans, run requests, reports, events, and registries;
- optional `uvicorn` extra for standalone development and serving;
- an SSE implementation selected after evaluating compatibility with current
  Starlette response streaming and cancellation behavior.

FastAPI must not become a core dependency. Heavy pipeline work must not run
through `BackgroundTasks`; production submission delegates to a durable
runtime, queue, or orchestrator.

### Secret-provider plugins

Pipelantic core should define `SecretRef`, `SecretValue`, and the Secret
Provider protocol without requiring a secret-manager SDK.

| Provider concept | Packages | Decision |
|---|---|---|
| Local workstation | `keyring` | Preferred local provider using OS credential stores |
| AWS Secrets Manager | `boto3`; optional `aws-secretsmanager-caching` | Separate plugin; prefer IAM roles and explicit caching |
| Azure Key Vault | `azure-keyvault-secrets`, `azure-identity` | Separate plugin; prefer managed identity |
| Google Cloud Secret Manager | `google-cloud-secret-manager` | Separate plugin; prefer workload identity |
| HashiCorp Vault | `hvac` | Separate plugin; expose leases, renewal, revocation, and dynamic credentials |
| 1Password | `onepassword-sdk` | Optional plugin; evaluate after core conformance |

`keyring` is preferable to depending directly on Linux `SecretStorage` because
it supplies a cross-platform interface to supported system credential stores.

Pydantic `SecretStr` and `SecretBytes` are useful protected value types at
configuration boundaries, but they do not retrieve, rotate, lease, or revoke
secrets. `pydantic-settings` may be evaluated for application configuration and
mounted secret files; it should not become Pipelantic's provider abstraction.

The AWS cache package is not a universal cache layer. AWS documents that it is
not security hardened and does not force cache invalidation. Provider caching
must remain bounded, scoped, configurable, and covered by rotation tests.

## Packages to Evaluate but Not Adopt Yet

### Pluggy

Pluggy is a high-quality plugin and hook system proven by pytest. It supports
hook specifications, multiple implementations, ordering, wrappers, and tracing.

Pipelantic should not make it a hard dependency initially because:

- execution plugins are capability-bearing objects rather than primarily
  multi-subscriber hooks;
- lifespan, middleware, resources, callbacks, and providers already have
  distinct semantics;
- `importlib.metadata` handles package discovery;
- an internal typed registry is easier to secure and serialize.

Re-evaluate Pluggy if the SDK develops many true one-to-many extension hooks
whose ordering and wrapper behavior would otherwise be reimplemented.

### NetworkX

NetworkX offers a mature collection of DAG algorithms, including ancestors,
descendants, topological generations, closure, reduction, and longest paths.

Do not make it a runtime dependency for the first milestones. Pipelantic
needs a strongly typed, deterministic, source-aware graph whose diagnostics and
identity rules it owns. The standard library plus small owned algorithms should
cover the initial DAG requirements.

Use NetworkX as a development oracle in property tests. Re-evaluate it for
workspace-scale lineage and advanced post-1.0 graph analysis.

### Msgspec and Orjson

Both can provide high-performance serialization. Do not adopt them before
benchmarks prove Pydantic and the standard library miss an explicit performance
budget.

The public serialization schemas must remain independent of the encoder.

### Platformdirs

`platformdirs` is well suited to user cache and configuration locations. Add it
to the CLI extra if Pipelantic begins storing user-level state. Do not add it
before that need exists.

## Development Dependencies

Recommended development toolchain:

| Area | Packages |
|---|---|
| Test runner | `pytest`, `pytest-cov`, `pytest-xdist` |
| Property and state-machine testing | `hypothesis` |
| Async tests | AnyIO's pytest plugin |
| Formatting and linting | `ruff` |
| Static typing | `pyright`, with `mypy` compatibility where plugin authors need it |
| Dependency boundaries | `grimp` or import-linter, plus `deptry` |
| Security | `pip-audit`, `bandit`, `detect-secrets` |
| Build and publishing | `uv`, `build`, `twine` |
| Documentation | `mkdocs`, `mkdocs-material`, `mkdocstrings[python]` |
| Benchmarks | `pytest-benchmark`, `pyperf` |
| Mutation testing | `mutmut` or `cosmic-ray` selectively |

Hypothesis is particularly valuable for:

- arbitrary DAG generation;
- cycle and dependency-closure tests;
- plan determinism;
- serialization round trips;
- migration compatibility;
- cancellation and state-machine behavior;
- parser and resolver security limits.

Property tests should compare selected graph results against NetworkX as an
independent oracle during development.

## Proposed Installation Groups

```toml
[project]
dependencies = [
    "contractmodel>=<validated-lower>,<<next-breaking>",
    "pydantic>=2.12,<3",
    "anyio>=4,<5",
    "packaging>=24",
    "typing-extensions>=4.12; python_version < '3.13'",
]

[project.optional-dependencies]
yaml = ["ruamel.yaml>=0.18,<0.20"]
jsonschema = ["jsonschema>=4.25,<5", "referencing>=0.36,<1"]
cli = ["cyclopts>=4,<5", "rich>=14,<15"]
http = ["httpx>=0.28,<1"]
observability = ["opentelemetry-api>=1.36,<2"]
notebook = ["ipython>=8,<11", "ipywidgets>=8,<9"]
docs-rendering = [
    "jinja2>=3.1,<4",
    "markdown-it-py>=4,<5",
    "graphviz>=0.21,<1",
]
```

These are candidate ranges and must be validated against the actual minimum
Python version and ContractModel release before being copied into
`pyproject.toml`.

Backend distributions should define their own dependencies rather than placing
them in the core project's optional-dependency table.

## Dependency Decision Matrix

| Package | Tier | Decision |
|---|---|---|
| ContractModel | Core | Adopt when public integration API is stable |
| Pydantic | Core | Adopt |
| AnyIO | Core | Adopt |
| Packaging | Core | Adopt |
| Typing Extensions | Core, conditional | Adopt only as required |
| ruamel.yaml | Extra | Adopt for source-preserving YAML |
| jsonschema + referencing | Extra | Adopt for portable schema validation |
| Cyclopts + Rich | CLI extra | Adopt |
| HTTPX | HTTP extra | Adopt behind network policy |
| OpenTelemetry API | Observability extra | Adopt |
| IPython | Notebook extra | Adopt for rich display integration |
| Ipywidgets | Notebook extra | Adopt for optional interactive controls |
| nbformat + nbclient | Development/docs | Use to verify example notebooks in CI |
| Claude, OpenAI, or Cursor SDKs | Separate adapter only | Do not add to core or documentation generators |
| MCP Python SDK | Optional AI tooling extra | Evaluate for a read-only inspection server |
| Structlog | Provider | Support, do not require |
| Jinja2 + Markdown-It | Docs extra | Adopt with escaping |
| Graphviz Python package | Visualization extra | Adopt |
| Polars | Separate plugin | Adopt as reference backend |
| Pandas | Separate plugin | Adopt as compatibility backend |
| PyArrow | Plugin/interchange extra | Adopt where interchange requires it |
| SQLAlchemy Core | SQL plugin | Adopt |
| SQLGlot | SQL plugin, provisional | Evaluate with concrete AST use cases |
| Fsspec | Storage plugin | Adopt |
| Tenacity | Runtime/provider implementation | Adopt behind portable retry policy |
| PySpark | Separate plugin | Adopt |
| keyring | Local secret-provider plugin | Adopt |
| boto3 + AWS caching client | AWS secret-provider plugin | Adopt; caching optional |
| azure-keyvault-secrets + azure-identity | Azure secret-provider plugin | Adopt |
| google-cloud-secret-manager | GCP secret-provider plugin | Adopt |
| hvac | Vault secret-provider plugin | Adopt |
| onepassword-sdk | Optional secret-provider plugin | Evaluate after provider conformance |
| Pluggy | Deferred | Re-evaluate if true hook requirements grow |
| NetworkX | Development/post-1.0 | Use as test oracle; avoid core dependency |
| Msgspec/orjson | Deferred | Add only after benchmarks |

## Review Cadence

Review hard dependencies before every minor release and all dependencies before
every major release.

The review should record:

- current supported and tested versions;
- new transitive dependencies;
- known vulnerabilities and advisories;
- license compatibility;
- wheel availability for supported platforms;
- import-time and installation-size impact;
- deprecations affecting Pipelantic;
- whether the dependency still earns its tier.

The goal is not zero dependencies. The goal is a small set of excellent
dependencies at clearly enforced architectural boundaries.

## Primary References

- [Pydantic package metadata](https://pypi.org/project/pydantic/)
- [AnyIO documentation](https://anyio.readthedocs.io/en/stable/)
- [Packaging version specifiers](https://packaging.pypa.io/en/latest/specifiers.html)
- [Python package metadata and entry points](https://docs.python.org/3/library/importlib.metadata.html)
- [ruamel.yaml documentation](https://yaml.dev/doc/ruamel.yaml/)
- [jsonschema documentation](https://python-jsonschema.readthedocs.io/en/stable/)
- [Cyclopts documentation](https://cyclopts.readthedocs.io/en/stable/)
- [Rich documentation](https://rich.readthedocs.io/en/stable/)
- [OpenTelemetry Python documentation](https://opentelemetry.io/docs/languages/python/)
- [SQLAlchemy Core documentation](https://docs.sqlalchemy.org/en/20/intro.html)
- [Fsspec documentation](https://filesystem-spec.readthedocs.io/en/stable/)
- [Tenacity documentation](https://tenacity.readthedocs.io/en/stable/)
- [Python keyring](https://keyring.readthedocs.io/en/stable/)
- [Pydantic secret types](https://docs.pydantic.dev/latest/api/types/#pydantic.types.SecretStr)
- [AWS Secrets Manager Python caching](https://docs.aws.amazon.com/secretsmanager/latest/userguide/retrieving-secrets_cache-python.html)
- [Azure Key Vault Secrets Python client](https://learn.microsoft.com/en-us/python/api/overview/azure/keyvault-secrets-readme)
- [Google Cloud Secret Manager Python client](https://cloud.google.com/python/docs/reference/secretmanager/latest)
- [HashiCorp Vault client libraries](https://developer.hashicorp.com/vault/api-docs/libraries)
- [1Password SDKs](https://www.1password.dev/sdks/)
- [Pluggy documentation](https://pluggy.readthedocs.io/en/stable/)
- [NetworkX DAG algorithms](https://networkx.org/documentation/stable/reference/algorithms/dag.html)
- [Hypothesis documentation](https://hypothesis.readthedocs.io/en/latest/)
- [pytest documentation](https://docs.pytest.org/en/stable/)
