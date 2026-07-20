# ADR-014: SOLID Core Refactor (UI-stable)

Date: 2026-07-20  
Status: Accepted

## Context

Core modules (`planner.py`, `orchestrator.py`, `validation.py`, `pipeline.py`,
`lifecycle/runtime.py`) grew large and duplicate engine classification, plugin
discovery, and portable-transform policy logic. Future engine families and
plugins require editing multiple switch statements.

## Decision

Refactor `src/etlantic` using SOLID principles behind **unchanged public
surfaces**:

- SDK exports in `etlantic.__init__.__all__`
- CLI command names, flags, and JSON/SARIF outputs
- Plugin entry-point groups and factory names
- `PipelinePlan`, `PipelineRunReport`, diagnostic codes, plan fingerprints
- Orchestration protocol (`compile_plan`, `OrchestratorPlugin`)

Internal layout:

| Package | Responsibility |
|---|---|
| `etlantic.plugins` | Shared plugin discovery coordinator |
| `etlantic.engines` | Engine family registry and priority |
| `etlantic.planning` | Plan builder stages |
| `etlantic.validation.phases` | Validation phase modules |
| `etlantic.runtime.executors` | Engine executor registry |
| `etlantic.authoring` | Pipeline graph construction |
| `etlantic.cli.cmds` | CLI command modules |

Strangler-fig: extract collaborators; keep facades in original modules.

## Frozen regression gates

Every phase merge requires:

```bash
./scripts/test_core.sh
uv run python scripts/check_docs.py
uv run python scripts/check_surface_inventory.py
uv run etlantic validate examples/quickstart.py:CustomerPipeline --format sarif
uv run python examples/quickstart.py
```

## Consequences

- God modules shrink; new engines register via `EngineFamily` + `EngineExecutor`
- No user-facing API migration for 0.21.x
- Plugin packages (`etlantic-polars`, etc.) deferred to a follow-on effort
