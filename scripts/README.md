# Scripts

Maintainer and CI helpers under `scripts/`. Prefer the paths documented in
[Contributing](https://etlantic.readthedocs.io/en/latest/11_DEVELOPMENT/CONTRIBUTING/) and
[Release process](https://etlantic.readthedocs.io/en/latest/11_DEVELOPMENT/RELEASE_PROCESS/).

| Script | Purpose | CI |
|---|---|---|
| `check_pyright.sh` | Repository-wide strict Pyright gate, shadow scan, and locked exception inventory | Checks |
| `test_core.sh` | Strict Pyright plus marker-aware core pytest (excludes optional plugin markers) | Checks (via docs/CONTRIBUTING parity) |
| `check_docs.py` | Version stamps, banned phrases, trust-example gate, docstring gate | Checks |
| `check_runnable_docs.py` | Invoked by `check_docs.py` for runnable-doc invariants | Checks |
| `check_pipeline_codec_burn_in.py` | `etlantic.pipeline/1` golden burn-in (`v0_24`–`v0_27`) | Checks |
| `check_codec_burn_in_matrix.py` | Cross-artifact burn-in matrix (`v0_24`–`v0_27`) | Checks |
| `check_plugin_manifests.py` | Plugin manifest digests / trust metadata | Checks |
| `check_agent_guidance.py` | AGENTS.md / agent surface consistency | Checks |
| `check_release.py` | Release readiness (versions, packages) | Checks |
| `bump_version.py` | Synchronize lockstep package versions, current-facing references, lockfile, and manifest digests | [Version bump workflow](../docs/11_DEVELOPMENT/RELEASE_PROCESS.md#version-bump-workflow) |
| `check_registry_conformance.py` | CP2 registry promote/suspend (memory + SQLModel `--fake`) | Manual / optional |
| `check_registry_isolation.py` | CP2 two-tenant/two-workspace isolation + profile matrix (`--fake`) | Manual / optional |
| `check_surface_inventory.py` | Public surface inventory gate | Checks |
| `check_protocol_freeze.py` | Plugin SDK `/1` freeze vs surface inventory | Checks |
| `check_transform_compiler_drift.py` | Portable compiler drift across engines | Checks |
| `check_benchmarks.py` | Microbenchmark baseline gate | Benchmarks job |
| `build_docs.py` | Build MkDocs site | Checks |
| `generate_diagnostics_catalog.py` | Emit code→source diagnostics inventory | Manual / docs regen |

## Common recipes

```bash
# Preview and apply a lockstep 0.x.y package version bump
uv run python scripts/bump_version.py 0.58.0 --dry-run
uv run python scripts/bump_version.py 0.58.0
```

The preview lists affected tracked files. Applying the change also refreshes
`uv.lock`, plugin manifest digests, and the DuckDB 0.49 and adaptive 0.52
evidence bundles. The adaptive evidence refresh runs its qualification tests.
Review publication state, support wording, changelog notes, and remaining
version-derived fixtures afterward. Historical release prose remains intact;
docs `current_minor` markers are updated for a minor bump. See the [full
workflow](../docs/11_DEVELOPMENT/RELEASE_PROCESS.md#version-bump-workflow)
before using this for a release.

```bash
# Docs-only PR
uv run ruff check .
uv run python scripts/check_docs.py
uv run python scripts/build_docs.py

# Core CI-equivalent (see CONTRIBUTING for the full list)
./scripts/test_core.sh  # includes the repository-wide strict Pyright gate
uv run python scripts/check_docs.py
uv run python scripts/check_pipeline_codec_burn_in.py
uv run python scripts/check_codec_burn_in_matrix.py
uv run python scripts/check_plugin_manifests.py

# Regenerate diagnostics catalog (keep status banner if present)
uv run python scripts/generate_diagnostics_catalog.py --markdown \
  > docs/10_REFERENCE/DIAGNOSTICS_CATALOG.md
```
