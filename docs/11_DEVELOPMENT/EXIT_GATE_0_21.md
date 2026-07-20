# Exit Gate 0.21 — Cohesive CLI and Authoring Experience

| Deliverable | Status |
|---|---|
| `init → doctor → inspect → validate → plan → run → report` journey | Done |
| `etlantic init` minimal scaffold | Done |
| `etlantic doctor` read-only checks | Done |
| `profile validate/show/diff/migrate` | Done |
| Declarative asset configuration (URI/object) | Done |
| Durable workspace + file report store default | Done |
| Cross-invocation report discovery | Done |
| Global CLI output options | Done |
| Exit code taxonomy | Done |
| Mutation preamble / `--preview` | Done |
| Diagnostic parity (human/json/sarif fields) | Done |
| `plan diff` + human explain | Done |
| Optional `etlantic.toml` + profiles fallback | Done |
| Legacy bindings fail-closed (PMCFG111) | Done |
| Docs + migration guide | Done |

## Acceptance scenarios

- New user can initialize, validate, plan, run, and inspect a durable report in
  separate shell invocations (`tests/cli/test_workspace.py`).
- Quickstart path no longer requires process-local memory seeding when using
  init scaffold + json assets.
- Mutating commands support `--preview` where applicable (`run`, `compile`).
- Help/completion smoke tests stable (`tests/cli/test_help_snapshots.py`).

## Residual notes

- Root SDK `__all__` remains broad; use [Surface Inventory](../10_REFERENCE/SURFACE_INVENTORY.md)
  for the recommended stable set. Further slimming targets 0.22+.
- `ArtifactStore` durable writes still use direct filesystem I/O; SafeIoPolicy
  integration for artifacts is a follow-up hardening item.
