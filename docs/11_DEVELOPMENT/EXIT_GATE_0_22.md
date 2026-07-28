# Exit Gate 0.22 — Plugin SDK Release Candidate

| Deliverable | Status |
|---|---|
| Capability-driven engine identity (no first-party name privileges) | Done |
| Synthetic third-party engine end-to-end tests | Done |
| Capability vocabulary `etlantic.capabilities/1` + policy doc | Done |
| Typed protocol metadata (`ExecutionContextMeta` / `CompileArtifactMeta`) | Done |
| Public conformance hardening + Spark suite + truthfulness helpers | Done |
| First-party plugins tested only via public `etlantic.testing` | Done |
| `etlantic plugin compatibility` CLI | Done |
| Curated `import etlantic as etl` facade + lazy namespaces | Done |
| Surface inventory + import-budget + typing fixtures | Done |
| `PROTOCOL_EVOLUTION.md` (freeze-eligible, not frozen) | Done |
| Out-of-monorepo `etlantic-plugin-echo` + CI clone job | Done |
| Docs: What's New / Migration / this exit gate | Done |
| Core + plugins bumped to 0.22.0 | Done |

## Acceptance checklist

- [x] Third-party-named engine works validate→plan→run/compile→report→viz without core name privileges (`tests/unit/test_engine_identity_0_22.py`)
- [x] Reserved/first-party name alone cannot unlock behavior
- [x] Overstated capabilities fail conformance with actionable codes (`tests/unit/test_conformance_hardening_0_22.py`)
- [x] First-party plugins use public `etlantic.testing` entry points (no private underscore imports)
- [x] `etlantic plugin compatibility` works from installed metadata (`tests/unit/test_plugin_compatibility_0_22.py`)
- [x] `etlantic-plugin-echo` public repo + monorepo CI workflow (`.github/workflows/external-plugin-echo.yml`)
- [x] `import etlantic as etl` minimal, typed, lazy namespaces, identity-stable (`tests/unit/test_root_facade.py`)
- [x] Surface inventory + import budget + typing fixtures enforce ownership
- [x] No architectural dependency on first-party engine identity sets in planner/coordinator/runtime
- [ ] Protocol `/1` **frozen** — **done in 0.28.0**; see [EXIT_GATE_0_28](EXIT_GATE_0_28.md)

## Freeze note

Protocol `/1` is **freeze-eligible** after:

1. Echo CI job green against published 0.22 core on PyPI (post-tag)
2. At least **one** external feedback cycle from a non-first-party plugin author
3. No open blockers on packaging assumptions discovered by echo

Until then, 0.22 ships as a **Release Candidate** for the Plugin SDK. Additive
optional methods and vocabulary clarifications may still land in `/1`.

## External proof

- Repo: https://github.com/eddiethedean/etlantic-plugin-echo
- Workflow: `.github/workflows/external-plugin-echo.yml`
  (`workflow_dispatch`, weekly schedule, `external-plugin` PR label, and
  relevant path pushes)

## Residual / follow-ups (0.23+)

- Runtime resilience budgets and failure injection at every boundary
- Multi-worker control plane
- Storage / Resource / Observability protocol catalogs (remain Design Proposals)
- Declaring multi-tenant unrestricted production
- Full pyright fail-suite CI gate for `tests/typing/fail`
