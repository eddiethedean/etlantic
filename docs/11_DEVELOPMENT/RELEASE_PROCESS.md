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
Official plugins declare `etlantic>=0.46.0,<0.47`.

## Package categories

| Category | Examples | Classifier | Docs maturity |
|---|---|---|---|
| Core | `etlantic` | Beta | Beta / single-tenant pilots |
| Execution plugins | `etlantic-polars`, `etlantic-sql`, … | Beta | **Same Beta product envelope** as core — supported execution adapters for pilots, not unrestricted enterprise readiness |
| Facade | `medallantic` | Beta (IR/migration adapter; not a full runtime) | Beta |
| Compatibility redirect | `etlantic-sparkforge` | Inactive (final release) | Deprecated redirect |
| Reference adapter | `etlantic-fastapi` | Beta | Beta |
| Reference adapter | `etlantic-lsp` | Beta | Beta |
| Experimental | `etlantic-datafusion` | Alpha | Experimental |

See [Facade packages](FACADE_PACKAGES.md). Evaluators should treat narrative
Beta / single-tenant boundaries in [Capabilities](../01_GETTING_STARTED/CAPABILITIES.md)
as authoritative over PyPI classifier wording.

## Packages published on each tag

Tag `vX.Y.Z` publishes twenty distributions:

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
| `medallantic` | `packages/medallantic` | **facade** |
| `etlantic-sparkforge` | `packages/etlantic-sparkforge` | **compatibility redirect** → medallantic |
| `etlantic-fastapi` | `packages/etlantic-fastapi` | thin reference adapter (since 0.24) |
| `etlantic-lsp` | `packages/etlantic-lsp` | language server host (since 0.44) |
| `etlantic-datafusion` | `packages/etlantic-datafusion` | **Experimental** (Alpha classifier) |
| `etlantic-s3` | `packages/etlantic-s3` | **Experimental** connector (Alpha classifier) |
| `etlantic-kafka` | `packages/etlantic-kafka` | **Experimental** Kafka reference (Alpha; fake-first) |
| `etlantic-schemaregistry` | `packages/etlantic-schemaregistry` | **Experimental** Confluent-compatible registry (Alpha; fake-first) |
| `etlantic-iceberg` | `packages/etlantic-iceberg` | **Experimental** connector (Alpha classifier) |
| `etlantic-snowflake` | `packages/etlantic-snowflake` | **Experimental** connector (Alpha classifier) |
| `etlantic-openlineage` | `packages/etlantic-openlineage` | **Experimental** outbound OpenLineage (Alpha) |

VS Code reference extension lives at `editors/vscode` (VSIX; not a PyPI
wheel). Build with `npm run package` after `npm install`.

## Pre-Release Checklist

1. Confirm milestone scope against
   [ROADMAP](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md) and
   [CAPABILITIES](../01_GETTING_STARTED/CAPABILITIES.md).
2. Resolve release-blocking issues; `main` CI must be green.
3. Confirm every package version and `__version__` equals the intended tag
   (no `v` prefix). Extras pins use `==X.Y.Z`.
   When plugin manifest JSON changes, regenerate digests:

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
   For 0.38.0, `etlantic-s3`, `etlantic-iceberg`, and `etlantic-snowflake` are
   brand-new PyPI names—pace new-project creates accordingly.
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
    cut a new patch version.

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
2. Verifies tag == core + all plugin versions.
3. Builds all twenty wheels/sdists.
4. Smokes the core wheel (driver-free) **and** plugin discovery/import
   **before** any PyPI upload.
5. Publishes to PyPI: **existing projects first** (thirteen established
   projects, then the three new 0.38 experimental connector projects),
   **10-minute** gaps only between brand-new project creates; skips files
   already present via `--check-url`; retries on transient 429s.
6. Creates the GitHub Release from `CHANGELOG.md` notes when publish succeeds.

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
**0.46** plugins, `etlantic>=0.46.0,<0.47`). A core
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
