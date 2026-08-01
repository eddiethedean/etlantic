# Contributing

> **Status: Available in ETLantic 0.41.0.**

ETLantic welcomes contributions to documentation, typed authoring APIs,
validation, planning, plugins, tests, and examples.

Preserve the boundaries established in the manifesto and foundations
documentation: ETLantic owns the logical model; plugins own execution;
standards own semantics.

## Contributor ladders (pick one)

| Ladder | Time | Checks | Scope |
|---|---|---|---|
| **Docs / typo** | ~30 min | ruff + `check_docs` + `check_agent_guidance` | Markdown, nav, examples prose |
| **Core / plugin** | full CI-equivalent | `./scripts/test_core.sh` + authoring + docs + surface inventory | Runtime, plugins, schemas |
| **Release-impacting** | full + packaging | Everything in [Full CI-equivalent checks](#full-ci-equivalent-checks-core-plugin-release-impacting) | Version pins, manifests, wheels |

Docs-only PRs do **not** need the full pytest wall. Property-based suites in
[TESTING.md](TESTING.md) are aspirational — not a mandatory PR checklist.

## Before You Start

For **docs / typo / small fix PRs:** skim
[Architecture](../02_FOUNDATIONS/ARCHITECTURE.md) and jump to
[Development Setup](#development-setup). Use the docs-only checks below.

For **core, plugin, or architecture PRs**, also read:

- [Manifesto](../ETLANTIC_MANIFESTO.md)
- [Design Principles](../02_FOUNDATIONS/DESIGN_PRINCIPLES.md)
- [Architecture](../02_FOUNDATIONS/ARCHITECTURE.md)
- [Design Decisions](DESIGN_DECISIONS.md)

Look for `good first issue` labels when they are present on the tracker.

## Scope Test

Ask:

1. Does this concern portable modeling, validation, or planning?
2. Is it execution behavior that belongs in a plugin?
3. Is it data-contract operational behavior that belongs in ContractModel?
4. Is it contract meaning that belongs in [ODCS](../03_DATA_CONTRACTS/ODCS.md), [DTCS](../04_TRANSFORMATIONS/DTCS.md), or [DPCS](../05_PIPELINES/DPCS.md)?

ETLantic owns the logical model. Plugins own execution. Standards own
semantics.

## Development Setup

```bash
git clone https://github.com/eddiethedean/etlantic.git
cd etlantic
git checkout -b topic/my-change
uv sync --locked
```

Always use `uv sync --locked` so your environment matches `uv.lock`.

`uv sync --locked` installs runtime dependencies, the editable workspace packages, and
the `dev` group (pytest, ruff, mkdocs). Optional groups: `dataframes`, `sql`,
`pyspark`, `airflow`, `prefect`, `medallantic`, `keyring`, `sqlmodel`. The
workspace also includes experimental `etlantic-datafusion` (Alpha; not a
default group)—install via `uv sync --extra datafusion` or the package path
when working on Gate B. See
[Installation](../01_GETTING_STARTED/INSTALLATION.md).

Use the supported Python versions documented in `pyproject.toml` (3.11+).
PySpark real-cluster parity needs a JVM; default Spark tests use sparkless.
Airflow tests need the `airflow` group. PostgreSQL SQL tests need a live URL
via `ETLANTIC_SQL_URL` when not using the SQLite demo path.

## Fail-closed contributor rules

Mirror [AGENTS.md](https://github.com/eddiethedean/etlantic/blob/main/AGENTS.md):

- Prefer public SDK imports; do not rely on private underscore modules.
- Never embed secret values in plans, reports, contracts, or docs.
- Production profiles require `plugin_allowlist` and fail closed.
- Schema history stores fingerprints/metadata only—never source rows.
- Medallion bronze/silver/gold stay in SparkForge / `medallantic`.

## Minimal first PR (docs-only or tiny fix)

```bash
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run python scripts/check_docs.py
uv run python scripts/check_agent_guidance.py
```

Then open a PR against `main`.

Security vulnerabilities: follow the private process in
[SECURITY.md](https://github.com/eddiethedean/etlantic/blob/main/SECURITY.md)
— do not open a public issue with exploit details.

## Full CI-equivalent checks (core / plugin / release-impacting)

Use this longer checklist for changes that touch runtime, plugins, schemas,
or release packaging. Docs-only PRs do **not** need the full list.
Baseline (core + docs):

```bash
uv sync --locked
uv run ruff check .
uv run ruff format --check .
./scripts/test_core.sh
# equivalent:
# uv run pytest -q -m "not medallantic and not polars and not pandas and not sql and not spark and not real_pyspark and not airflow and not prefect and not keyring and not sqlmodel and not datafusion"
uv run pytest -q tests/authoring
uv sync --extra fastapi
uv run pytest -q packages/etlantic-fastapi/tests
uv run python examples/pipeline_definition_json.py
uv run python scripts/check_docs.py
uv run python scripts/check_pipeline_codec_burn_in.py
uv run python scripts/check_codec_burn_in_matrix.py
uv run python scripts/check_plugin_manifests.py
uv run python scripts/check_agent_guidance.py
uv run python scripts/check_release.py
uv run python scripts/check_surface_inventory.py
uv run python scripts/check_transform_compiler_drift.py
uv run python -m etlantic validate examples/memory_customers.py:CustomerPipeline --format sarif > /tmp/etlantic.sarif
uv run python examples/memory_customers.py
uv run python scripts/build_docs.py
# Optional performance gate (CI benchmarks job):
# uv run python scripts/check_benchmarks.py
```

Optional plugins / portable examples:

```bash
uv sync --locked --group dataframes
uv run python examples/portable_polars_kernel.py
uv run python examples/portable_pandas_kernel.py
uv run pytest -q -m "polars or pandas"
uv sync --locked --group medallantic
uv run pytest -q tests/medallantic -m medallantic
```

## Making a Change

1. Fork and open a branch from `main` (or identify an issue).
2. Confirm the architectural owner of the feature.
3. Add an ADR for difficult-to-reverse architectural changes.
4. Add tests before or with implementation.
5. Update affected documentation.
6. Update `CHANGELOG.md` under `[Unreleased]` for user-visible changes (no
   separate fragment tool is required today).
7. Run the CI-equivalent checks above.

## Pull Requests

Pull requests should include:

- Problem statement
- Proposed behavior
- Public API impact
- Contract or plugin compatibility impact
- Tests
- Documentation changes
- Performance or security considerations

Keep pull requests focused. Separate unrelated refactoring from behavior
changes.

## Public API Changes

Changes to root imports, authoring syntax (`etlantic.authoring` /
`PipelineDefinition`), plugin protocols, `PipelinePlan`, or generated contract
meaning require extra review. Treat
[PROGRAMMATIC_AUTHORING_0_24.md](PROGRAMMATIC_AUTHORING_0_24.md) as a
**historical** design record—the shipped guide is
[Programmatic authoring](../05_PIPELINES/PROGRAMMATIC_AUTHORING.md).

Before adding a public abstraction, demonstrate at least two concrete consumers
or one complete end-to-end workflow that needs it.

## Documentation Contributions

Documentation should:

- Lead with the user outcome
- Use consistent terms from the glossary
- Distinguish proposed APIs from implemented APIs
- Link to normative standards instead of duplicating them
- Include executable examples where possible
- Avoid claiming that ETLantic executes work owned by plugins

See [Documentation Contributions](DOCUMENTATION.md) for page-status labels,
current-version rules, and CI checks.

### Preview docs locally

```bash
uv run python scripts/build_docs.py serve
# equivalent: uv run mkdocs serve
```

Open the printed local URL (typically `http://127.0.0.1:8000/`). Use
`uv run python scripts/build_docs.py` for the strict CI build.

## Plugin Contributions

Core plugins should:

- Depend only on public SDK interfaces
- Declare accurate capabilities
- Pass conformance tests
- Normalize diagnostics and failures
- Avoid importing heavy dependencies until needed
- Document supported backend versions

Third-party plugins may be maintained independently and distributed through
Python package entry points. Before opening a plugin PR, also run
`uv run python scripts/check_transform_compiler_drift.py` and
`uv run python scripts/check_surface_inventory.py` when touching compilers or
public surfaces.

## Testing

### Currently enforced

- `pytest` unit/CLI suites on CI
- `ruff check` / `ruff format --check`
- `scripts/check_docs.py` + runnable companions + strict MkDocs build
- Optional dataframe / SparkForge matrix jobs

### FastAPI optional package tests

`etlantic-fastapi` tests import repository `examples/`. From a checkout run:

```bash
PYTHONPATH=. uv run pytest tests/fastapi packages/etlantic-fastapi/tests
```

(or rely on the CI workflow path that already sets the correct roots).

### Currently enforced for portable compilers

- Public `run_portable_transform_conformance_suite` for Polars / Pandas / PySpark
- Hypothesis property tests for capability matching and fingerprint stability
- Compiler e2e / differential suites in CI dependency-group jobs

### Not yet enforced (aspirational)

Coverage thresholds, pyright, dependency audit, and secret scanning are
goals—not CI requirements. See [Testing](TESTING.md) and
[Dependency Strategy](DEPENDENCY_STRATEGY.md).

Run the narrowest relevant tests during development:

```bash
uv sync --group dataframes
uv run pytest -m polars
uv run pytest -m pandas
uv run pytest tests/polars_compiler
```

For Spark plugin work (JVM-free via sparkless by default):

```bash
uv sync --group pyspark
uv run pytest tests/spark
# Optional parity against real PySpark (requires Java):
SPARKLESS_TEST_MODE=pyspark uv run pytest tests/spark -m spark
```

For Airflow orchestrator work:

```bash
uv sync --group airflow
uv run pytest tests/orchestration tests/airflow
uv run python examples/airflow_compile.py
```

For Prefect scheduler work:

```bash
uv sync --group prefect
uv run pytest tests/prefect -m prefect
uv run python examples/prefect_run.py
```

The committed toolchain is uv + pytest + ruff + mkdocs.

## Commit Messages

Use concise, imperative summaries:

```text
Add typed multi-output step model
Validate SQL dialect capabilities during planning
Document plugin cancellation semantics
```

## Code of Conduct

Be respectful, specific, and constructive. Review the work rather than the
person. Assume good intent while asking for evidence on correctness,
compatibility, and architecture.

## Security Issues

Do not report credential leaks, arbitrary code execution, unsafe reference
resolution, or other vulnerabilities through a public issue. Follow the
repository security policy.
