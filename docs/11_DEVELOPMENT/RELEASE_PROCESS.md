# Release Process

ETLantic releases must coordinate the core package, optional plugins, generated
artifacts, compatibility policy, and documentation.

## Versioning

ETLantic follows Semantic Versioning after 1.0:

- Patch: compatible fixes and documentation
- Minor: backward-compatible capabilities
- Major: incompatible public API or persistent-format changes

During 0.x, breaking changes remain possible but must be documented. Official
plugin packages currently share the core minor version (for example `0.20.0`).

## Packages published on each tag

Tag `vX.Y.Z` publishes eleven distributions:

| PyPI name | Source | Notes |
|---|---|---|
| `etlantic` | repo root | core |
| `etlantic-polars` | `packages/etlantic-polars` | stable |
| `etlantic-pandas` | `packages/etlantic-pandas` | stable |
| `etlantic-sql` | `packages/etlantic-sql` | stable |
| `etlantic-pyspark` | `packages/etlantic-pyspark` | stable |
| `etlantic-airflow` | `packages/etlantic-airflow` | stable |
| `etlantic-prefect` | `packages/etlantic-prefect` | stable |
| `etlantic-keyring` | `packages/etlantic-keyring` | stable |
| `etlantic-sqlmodel` | `packages/etlantic-sqlmodel` | stable |
| `etlantic-sparkforge` | `packages/etlantic-sparkforge` | stable |
| `etlantic-datafusion` | `packages/etlantic-datafusion` | **Experimental** (Alpha classifier) |

## Pre-Release Checklist

1. Confirm milestone scope against
   [ROADMAP](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md) and
   [CAPABILITIES](../01_GETTING_STARTED/CAPABILITIES.md).
2. Resolve release-blocking issues; `main` CI must be green.
3. Confirm every package version and `__version__` equals the intended tag
   (no `v` prefix). Extras pins use `==X.Y.Z`.
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
   uv run pytest -q -m "not sparkforge and not polars and not pandas and not sql and not spark and not airflow and not prefect and not keyring and not sqlmodel"
   uv run python scripts/check_docs.py
   uv run python scripts/check_agent_guidance.py
   uv run python scripts/check_release.py
   uv run --group polars --group pandas --group sql --group pyspark python scripts/check_transform_compiler_drift.py
   uv run python scripts/build_docs.py
   uv sync --locked --group sparkforge
   uv run pytest -q tests/sparkforge -m sparkforge
   ```

7. **Normal path (stable projects already on PyPI):** publish uploads to
   existing projects. Prefer Trusted Publishing / OIDC when configured;
   otherwise use the least-privilege token documented for this repository.
   Treat long-lived user tokens and first-project bootstrap as exceptional.
   Experimental `etlantic-datafusion` may be a brand-new PyPI name on first
   publish—pace new-project creates accordingly.
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
3. Builds all eleven wheels/sdists.
4. Smokes the core wheel (driver-free) **and** plugin discovery/import
   **before** any PyPI upload.
5. Publishes to PyPI: **existing projects first** (including keyring/sqlmodel),
   then brand-new names (`etlantic-prefect`, `etlantic-sparkforge`);
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
| ODCS | Supported specification versions |
| DTCS | Supported specification versions |
| DPCS | Supported specification versions |
| Plugin SDK | API version |
| PipelinePlan | Schema version |

## Release Candidate

Major and high-risk minor releases should publish a release candidate:

```text
1.0.0rc1
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
0.18 plugins, `etlantic>=0.21.0,<0.22`). A core
release should not require third-party plugins to release simultaneously unless
the SDK compatibility range changes.

Official plugin releases should declare:

- Supported ETLantic versions
- Backend versions (when applicable)
- Capability changes
- Migration requirements

## Deprecations

After 1.0:

- Emit a documented warning.
- Provide a replacement.
- Include migration guidance.
- Retain deprecated behavior for at least one documented release window.
- Remove only in a major release unless security requires faster action.

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
- Monitor issue reports.
- Open follow-up issues for deferred work.
- Record lessons from release incidents.


## Supply chain (0.20+)

Release CI:

- writes per-artifact SHA-256 digests and `dist/sbom/release-artifacts.json`
- optionally emits CycloneDX environment SBOM when `cyclonedx-py` is available
- attests build provenance via GitHub Actions (`actions/attest-build-provenance`)
- prefers PyPI Trusted Publishing (OIDC); falls back to `UV_PUBLISH_TOKEN` only as bootstrap

Residual risk: long-lived tokens may remain until every distribution is configured for OIDC.
