# Release Process

ETLantic releases must coordinate the core package, optional plugins, generated
artifacts, compatibility policy, and documentation.

## Versioning

ETLantic's roadmap contains only 0.x phases. The 0.37 release is the stable
foundation, and post-foundation capabilities continue in later 0.x minors.

- Patch: compatible fixes and documentation within a minor line
- Minor: scheduled capabilities and any explicitly documented migrations
- Stable-foundation and later breaking changes: require a named 0.x migration
  phase, deprecation evidence, and persistent-format compatibility handling

Breaking changes must be documented. Official plugin packages currently share
the core minor version (for example `0.38.0`).
Official plugins and root extras declare the compatible 0.59 line floor
(`>=0.60.0`) without a patch lockstep pin or upper cap.

## Planned package truth and compatibility gates — 0.59 onward

F07/F10/F11 in the [package consolidation plan](PACKAGE_SCOPE_CONSOLIDATION_PLAN.md)
add release gates before expanding platform support. Generate each distribution's
version metadata from its manifest/build/installed metadata source; remove stale
hard-coded provider release strings and reconcile README scope claims. Protocol
versions are separate identifiers, not copies of package versions. Compare
registered factory metadata with installed distributions in a clean environment.

The factory inventory must report instantiated backend identity, live capability
and qualification separately. Exercise SDK present/absent × requested fake/live
× actual backend; an installed SDK cannot turn a fake into a live claim, and
unimplemented live requests must fail. Reference-only K8s, Spark Connect, Kafka
and MCP remain clearly labelled until actual live evidence passes.

For new minors, replace the current open floors with dependency constraints
matching the qualified core/runtime/plugin minor line, with resolver evidence
for supported patches and explicit exceptions. Update bump/lock tooling and
install guidance together; never infer cross-minor compatibility. These are
planned changes, not altered 0.58 manifests or historical qualification records.

The final `etlantic-sparkforge` compatibility wheel is **0.62.0**. Its visible
deprecation warning and migration window run from 0.59 through 0.62. Remove the
package from routine bump/build/publish lists and root extras starting with
0.63, after the 0.62 migration evidence is recorded; historic wheels remain.
Apply the same declared lifecycle to superseded reference fixture distributions.
New runtime/testing/HTTP wheels need an owner/extraction map and duplicate-
retirement evidence before release; conditional/deferred decisions stay explicit.

## Version bump workflow

Use `scripts/bump_version.py` for a lockstep release version change. It accepts
an increasing semantic `0.x.y` version and reads the current version from
`src/etlantic/_version.py`. Before applying it, make sure
`docs/release-facts.json` agrees with that version. The command works from the
repository checkout and considers tracked files only.

Preview first, then apply the same version:

```bash
uv run python scripts/bump_version.py 0.58.1 --dry-run
uv run python scripts/bump_version.py 0.58.1
```

The preview lists tracked version-surface files whose contents will change and
notes the generated refresh steps; it does not write files or run them.
Applying the bump synchronizes the
core and companion package versions, current-facing version references,
release-facts URLs, and the active changelog section. A minor bump also moves
open dependency floors and live `current_minor` page markers to the new minor.
It then runs `uv lock`, regenerates plugin manifest digests, and checks those
digests. It also regenerates and verifies the deterministic DuckDB 0.49
evidence bundle, whose package version and manifest digest track the current
release. It runs the adaptive 0.52 evidence campaign and refreshes its
source-bound bundle with `scripts/check_adaptive_0_52.py --write`, then runs the
verifier again. The campaign takes longer than the preview and a bump fails if
it fails. Historical changelog entries and evidence prose remain intact; live
current-minor page markers and generated evidence metadata stay synchronized.

### Adaptive evidence for gate updates

Adaptive 0.52 evidence is a CI gate. When a change updates the gate inputs or
their source-bound signatures outside a version bump, regenerate and verify the
evidence with:

```bash
uv run python scripts/check_adaptive_0_52.py --write
uv run python scripts/check_adaptive_0_52.py
```

The synchronizer does not decide whether the new version is published or a
candidate, write release notes, change support policy, or regenerate
version-derived test fixtures. Review and update these by hand:

- `docs/release-facts.json` publication state, dates, suitability, and support
  line; verify that the docs, PyPI, and GitHub release URLs are correct.
- `CHANGELOG.md` release notes and any migration guide. The command creates a
  basic `Changed` entry only when the current version has no unreleased
  section.
- `docs/CHANGELOG.md`, release-candidate wording, `SUPPORT.md`, and
  `SECURITY.md`, so they accurately distinguish the latest published version
  from the candidate.
- Any other changed version-derived fixtures or qualification artifacts.
  Inspect their diffs and regenerate them with the owning fixture or evidence
  workflow.

After review, verify synchronization and run the checks in the
[pre-release checklist](#pre-release-checklist). In particular, run
`uv sync --locked`, `scripts/check_docs.py`, `scripts/check_plugin_manifests.py`,
and `scripts/check_release.py` before tagging. The bump command does not create
a tag or publish packages.

## Package categories

| Category | Examples | Classifier | Docs maturity |
|---|---|---|---|
| Core | `etlantic` | Beta | Beta / single-tenant pilots |
| Execution plugins | `etlantic-polars`, `etlantic-sql`, … | Beta | **Same Beta product envelope** as core — supported execution adapters for pilots, not unrestricted enterprise readiness |
| Facade | `medallantic` | Beta (IR/migration adapter; not a full runtime) | Beta |
| Compatibility redirect | `etlantic-sparkforge` | Inactive (final release) | Deprecated redirect |
| Reference adapter | `etlantic-fastapi` | Beta | Beta |
| Reference adapter | `etlantic-lsp` | Beta | Beta |
| Provisional | `etlantic-datafusion` | Alpha | 0.50 technical qualification recorded and retained |

See [Facade packages](FACADE_PACKAGES.md). Evaluators should treat narrative
Beta / single-tenant boundaries in [Capabilities](../01_GETTING_STARTED/CAPABILITIES.md)
as authoritative over PyPI classifier wording.

## Packages published on each tag

Tag `vX.Y.Z` publishes twenty-five distributions (the core package and
twenty-four companion packages):

| PyPI name | Source | Notes |
|---|---|---|
| `etlantic` | repo root | core |
| `etlantic-polars` | `packages/etlantic-polars` | execution plugin |
| `etlantic-pandas` | `packages/etlantic-pandas` | execution plugin |
| `etlantic-sql` | `packages/etlantic-sql` | execution plugin |
| `etlantic-pyspark` | `packages/etlantic-pyspark` | execution plugin |
| `etlantic-airflow` | `packages/etlantic-airflow` | execution plugin |
| `etlantic-prefect` | `packages/etlantic-prefect` | execution plugin |
| `etlantic-keyring` | `packages/etlantic-keyring` | execution plugin |
| `etlantic-sqlmodel` | `packages/etlantic-sqlmodel` | execution plugin |
| `etlantic-foundry` | `packages/etlantic-foundry` | execution plugin; Foundry provider |
| `medallantic` | `packages/medallantic` | **facade** |
| `etlantic-sparkforge` | `packages/etlantic-sparkforge` | **compatibility redirect** → medallantic |
| `etlantic-fastapi` | `packages/etlantic-fastapi` | thin reference adapter (since 0.24) |
| `etlantic-lsp` | `packages/etlantic-lsp` | language server host (since 0.44) |
| `etlantic-datafusion` | `packages/etlantic-datafusion` | **Provisional** (Alpha classifier; 0.50 technical qualification recorded; independent review pending) |
| `etlantic-s3` | `packages/etlantic-s3` | **Experimental** connector (Alpha classifier) |
| `etlantic-kafka` | `packages/etlantic-kafka` | **Experimental** Kafka reference (Alpha; fake-first) |
| `etlantic-k8s` | `packages/etlantic-k8s` | **Experimental** Kubernetes resource provider (Alpha; FakeKubernetes) |
| `etlantic-spark-connect` | `packages/etlantic-spark-connect` | **Experimental** Spark Connect provider (Alpha; fake) |
| `etlantic-schemaregistry` | `packages/etlantic-schemaregistry` | **Experimental** Confluent-compatible registry (Alpha; fake-first) |
| `etlantic-iceberg` | `packages/etlantic-iceberg` | **Experimental** connector (Alpha classifier) |
| `etlantic-snowflake` | `packages/etlantic-snowflake` | **Experimental** connector (Alpha classifier) |
| `etlantic-openlineage` | `packages/etlantic-openlineage` | **Experimental** outbound OpenLineage (Alpha) |
| `etlantic-mcp` | `packages/etlantic-mcp` | **Experimental** read-only MCP extra (Alpha; FakeMcpServer) |
| `etlantic-duckdb` | `packages/etlantic-duckdb` | **Experimental** optional DuckDB SQL and portable-transform package |

VS Code reference extension lives at `editors/vscode` (VSIX; not a PyPI
wheel). Build with `npm run package` after `npm install`.

## Pre-Release Checklist

1. Confirm milestone scope against
   [ROADMAP](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md) and
   [CAPABILITIES](../01_GETTING_STARTED/CAPABILITIES.md).
2. Resolve release-blocking issues; `main` CI must be green.
3. Follow the [version bump workflow](#version-bump-workflow), then confirm
   every package version and `__version__` equals the intended tag (no `v`
   prefix). Root extras accept the matching minor line from its `.0` floor;
   deployment lockfiles may pin exact artifacts.

   To refresh manifest digests after changing manifest entries independently:

   ```bash
   uv run python scripts/check_plugin_manifests.py --write-digests
   uv run python scripts/check_plugin_manifests.py
   ```

4. Update
   [CHANGELOG.md](https://github.com/eddiethedean/etlantic/blob/main/CHANGELOG.md)
   (Added / Changed / Fixed / Upgrade notes) and migration guide when needed.
5. Confirm
   [SECURITY.md](https://github.com/eddiethedean/etlantic/blob/main/SECURITY.md)
   lists the currently supported release line and support policy.
6. Run local gates:

   ```bash
   uv sync --locked
   uv run ruff check .
   uv run ruff format --check .
   ./scripts/test_core.sh
   uv run python scripts/check_docs.py
   uv run python scripts/check_pipeline_codec_burn_in.py
   uv run python scripts/check_codec_burn_in_matrix.py
   uv run python scripts/check_plugin_manifests.py
   uv run python scripts/check_agent_guidance.py
   uv run python scripts/check_release.py
   uv run --group polars --group pandas --group sql --group pyspark --group datafusion python scripts/check_transform_compiler_drift.py
   uv run python scripts/build_docs.py
   uv sync --locked --group medallantic
   uv run pytest -q tests/medallantic -m medallantic
   ```

7. **Normal path (stable projects already on PyPI):** publish uploads to
   existing projects. Prefer Trusted Publishing / OIDC when configured;
   otherwise use the least-privilege token documented for this repository.
   Treat long-lived user tokens and first-project bootstrap as exceptional.
   For 0.56.0, `etlantic-foundry` is a brand-new PyPI name—pace its first
   project creation accordingly. Confirm the current project/version status
   with `scripts/check_release.py` for each release; names that were new in an
   earlier release may already exist.
8. **New distribution bootstrap only:** if introducing a brand-new PyPI name,
   review `scripts/check_release.py` output and PyPI new-project rate limits
   (`429 Too many new projects created`). Release CI waits between brand-new
   creates; existing projects upload immediately. If the account is still
   rate-limited for new projects, either wait for the rolling hour window or
   create empty projects manually on PyPI first so the release job only
   uploads versions.
9. Prefer tagging only the current release (do not `git push --tags`).
   Treat published tags as immutable. If a publish fails after the tag is
   public, prefer a new patch version rather than moving the tag.
10. If a prior tag’s publish job was cancelled mid-way before any public
    consumers rely on it, re-run that job until remaining packages land, or
    cut a new patch version. For a partial PyPI upload blocked by
    `429 Too many new projects created`, dispatch **Release** with the existing
    tag (`workflow_dispatch`, input `tag=vX.Y.Z`). Existing projects upload
    first and skip already-present files; the GitHub Release is created before
    remaining new names. Re-run later for any new project still rate-limited.

## Tag and publish (`X.Y.Z` example)

```bash
# On a clean main matching the intended commit:
git status
git pull --ff-only origin main

# Tag must match src/etlantic/_version.py (and every plugin package).
git tag -a vX.Y.Z -m "ETLantic X.Y.Z"
git push origin vX.Y.Z
```

GitHub Actions workflow
[release.yml](https://github.com/eddiethedean/etlantic/blob/main/.github/workflows/release.yml):

1. Runs the full checks matrix.
2. Verifies tag == core + lockstep plugin versions. The `etlantic-rsconnect`
   preview checks its metadata/module version independently of the core tag.
3. Builds the core and included optional wheels/sdists.
4. Smokes the core wheel (driver-free) **and** plugin discovery/import
   **before** any PyPI upload.
   The rsconnect preview has a separate installed-wheel smoke and uses its own
   version for artifact filenames and already-published checks. Preview
   `0.60.0` can therefore accompany core `0.60.0` without a monorepo version bump.
5. Publishes to PyPI: **existing projects first** (skip files already present
   via `--check-url`; retry transient 429s).
6. Creates the GitHub Release from `CHANGELOG.md` notes when existing-project
   publish succeeds.
7. Then publishes brand-new names (`etlantic-spark-connect`, `etlantic-mcp`)
   after the GitHub Release with `continue-on-error` and a **10-minute** gap
   so a new-project `429` cannot block the rest of the line. Re-dispatch
   **Release** later for any new name still rate-limited.

### Independently versioned Connect preview

`etlantic-rsconnect` has an independent release tag. Core `v0.60.0` already
exists and predates this package; keep that tag immutable. The 0.60.0 preview
was released from commit `def8a940` under
`etlantic-rsconnect-v0.60.0`; core remains at 0.60.0. The release validation
commands run against the intended clean release commit were:

```bash
uv sync --locked --extra rsconnect
uv run python scripts/check_rsconnect_release.py --tag etlantic-rsconnect-v0.60.0
uv run pytest -q tests/rsconnect tests/control_plane/test_trigger_0_59.py \
  tests/service/test_schedule_application_0_57.py
uv build --package etlantic-rsconnect
```

The [release workflow run](https://github.com/eddiethedean/etlantic/actions/runs/38656000427)
completed successfully and published the adapter wheel and sdist, then created
the [GitHub prerelease](https://github.com/eddiethedean/etlantic/releases/tag/etlantic-rsconnect-v0.60.0).
It ran the full checks, checked the installed adapter against released core
0.60.0, proved base installation needs no SDK or ETL engines, and ran the
focused tests with workspace imports disabled. Re-dispatch **Release** with the
same preview tag to retry an upload; existing artifacts are checked by
`uv publish --check-url`.

This path uses the existing `pypi` publishing environment and `release.yml`
Trusted Publishing identity. It requires no live Connect, Quarto, PostgreSQL,
receiver, or worker qualification. See the [0.60 exit record](EXIT_GATE_0_60.md)
for the distinction between a complete preview and deferred production support.

## After PyPI succeeds

1. Verify `pip install etlantic==X.Y.Z` and plugin extras from a clean venv.
2. Create or confirm the GitHub Release for `vX.Y.Z`.
3. Confirm install docs remain pip-first (`README.md`,
   `docs/01_GETTING_STARTED/INSTALLATION.md`) and hosted docs
   (`https://etlantic.readthedocs.io/`) build for the tag.
4. Monitor issues for install / import regressions.

## Compatibility Matrix

Release notes should state:

| Surface | Supported versions |
|---|---|
| Python | Project-defined range (`>=3.11`) |
| ContractModel | Compatible range |
| [ODCS](../03_DATA_CONTRACTS/ODCS.md) | Supported specification versions |
| [DTCS](../04_TRANSFORMATIONS/DTCS.md) | Supported specification versions |
| [DPCS](../05_PIPELINES/DPCS.md) | Supported specification versions |
| Plugin SDK | API version |
| PipelinePlan | Schema version |

## Release Candidate

Major and high-risk minor releases should publish a release candidate:

```text
0.38.0rc1
```

Validate installation, end-to-end examples, external plugin compatibility, and
migration documentation before final release.

## Build

The release pipeline should:

1. Build source and wheel artifacts.
2. Inspect package metadata.
3. Install from built artifacts in clean environments.
4. Run smoke tests.
5. Verify type information is included.
6. Verify optional dependencies remain optional.

## Publish

Recommended order:

1. Confirm brand-new PyPI names via `scripts/check_release.py` (first upload
   creates each project; there is no empty-project pre-register UI).
2. Optionally publish to TestPyPI and smoke-test.
3. Create the annotated release tag and push **that tag only**.
4. Let GitHub Actions publish to PyPI after checks.
5. Confirm the GitHub release and documentation links.
6. Announce plugin compatibility updates.

## Plugin Releases

Plugins are separately installable and declare a tested minor bound (for
**0.55** plugins, `etlantic>=0.55.0,<0.56`). A core
release should not require third-party plugins to release simultaneously unless
the SDK compatibility range changes.

Official plugin releases should declare:

- Supported ETLantic versions
- Backend versions (when applicable)
- Capability changes
- Migration requirements

## Deprecations

After the 0.38 stable foundation:

- Emit a documented warning.
- Provide a replacement.
- Include migration guidance.
- Retain deprecated behavior for at least one documented release window.
- Remove only in an explicitly scheduled 0.x migration phase unless security
  requires faster action.

## Plan and Configuration Migrations

Persistent `PipelinePlan` or configuration changes require:

- A schema/version change
- A migration tool or clear regeneration path
- Compatibility tests
- Release-note examples

Generated plans should normally be regenerated rather than hand-edited.

## Hotfixes

Security and critical correctness fixes may use an accelerated process, but
must still include focused tests, release notes, and artifact verification.

## Failure recovery

| Failure | Action |
|---|---|
| Checks fail before publish | Fix on `main`, retag only after green CI |
| Wheel smoke fails before publish | Do not publish; fix and retag |
| Partial PyPI upload (some packages done) | Re-run the release job; already-uploaded filenames are skipped |
| Bad artifact already on PyPI | Yank the defective file(s), publish a forward-fix patch, announce |
| Compromised `PYPI_API_TOKEN` | Revoke immediately, rotate, audit recent uploads |
| GitHub Release missing after PyPI | Re-run the create-release step or create manually from `CHANGELOG.md` |

Release approval authority sits with the lead maintainer
([MAINTAINERS.md](https://github.com/eddiethedean/etlantic/blob/main/MAINTAINERS.md)).
Prefer forward-fix patches over yanks unless the artifact is unsafe.

## Post-Release

After publishing:

- Verify package installation.
- Verify documentation links and the Read the Docs build for the tag.
- Activate the git tag under Read the Docs → **Versions** so
  `https://etlantic.readthedocs.io/en/vX.Y.Z/` is immutable and returns 200.
  Keep **latest** = `main` and **stable** = newest published tag. Update root
  and package README absolute docs links to `/en/vX.Y.Z/` (see
  `docs/release-facts.json`).
- Monitor issue reports.
- Open follow-up issues for deferred work.
- Record lessons from release incidents.


## Supply chain (0.20+)

Release CI:

- writes per-artifact SHA-256 digests and `dist/sbom/release-artifacts.json`
- optionally emits a CycloneDX environment SBOM when `cyclonedx-py` is
  available; on failure it uploads `sbom-warning.txt` instead
- attests build provenance via GitHub Actions (`actions/attest-build-provenance`)
- prefers PyPI Trusted Publishing (OIDC); falls back to `UV_PUBLISH_TOKEN` only as bootstrap

Public docs must describe the **actual** release assets. Do not claim SPDX or
CycloneDX SBOM when only digests / `sbom-warning.txt` shipped. Adopter-facing
checklist: [Release artifact verification](../01_GETTING_STARTED/RELEASE_ARTIFACT_VERIFICATION.md).

Residual risk: long-lived tokens may remain until every distribution is configured for OIDC.

## Documentation cutover (before announce)

1. Confirm PyPI serves the tagged version for core and official plugins.
2. Confirm GitHub Release assets: digests, attestations, and SBOM **or**
   `sbom-warning.txt`.
3. Confirm Installation / Quickstart pin that version (no day-0 `git+…@main`).
4. Confirm enterprise / security pages match assets.
5. Announce only after steps 1–4 pass (`check_docs` / `check_release`).

Migration definition and plan goldens include adapter provenance, planner and
plugin release versions. After a lockstep version bump, verify that canonical
inputs differ only in those version fields before refreshing their expected
fingerprints. Keep semantic, source, asset and node assertions intact; do not
refresh goldens to conceal behavioral changes.
