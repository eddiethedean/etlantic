# Release Process

ETLantic releases must coordinate the core package, optional plugins, generated
artifacts, compatibility policy, and documentation.

## Versioning

ETLantic follows Semantic Versioning after 1.0:

- Patch: compatible fixes and documentation
- Minor: backward-compatible capabilities
- Major: incompatible public API or persistent-format changes

During 0.x, breaking changes remain possible but must be documented. Official
plugin packages currently share the core minor version (for example `0.13.0`).

## Packages published on each tag

Tag `vX.Y.Z` publishes nine distributions:

| PyPI name | Source |
|---|---|
| `etlantic` | repo root |
| `etlantic-polars` | `packages/etlantic-polars` |
| `etlantic-pandas` | `packages/etlantic-pandas` |
| `etlantic-sql` | `packages/etlantic-sql` |
| `etlantic-pyspark` | `packages/etlantic-pyspark` |
| `etlantic-airflow` | `packages/etlantic-airflow` |
| `etlantic-keyring` | `packages/etlantic-keyring` |
| `etlantic-sqlmodel` | `packages/etlantic-sqlmodel` |
| `etlantic-sparkforge` | `packages/etlantic-sparkforge` |

## Pre-Release Checklist

1. Confirm milestone scope against [ROADMAP](ROADMAP.md) and
   [CAPABILITIES](../01_GETTING_STARTED/CAPABILITIES.md).
2. Resolve release-blocking issues; `main` CI must be green.
3. Confirm every package version and `__version__` equals the intended tag
   (no `v` prefix). Extras pins use `==X.Y.Z`.
4. Update
   [CHANGELOG.md](https://github.com/eddiethedean/etlantic/blob/main/CHANGELOG.md)
   (Added / Changed / Fixed / Upgrade notes) and migration guide when needed.
5. Confirm
   [SECURITY.md](https://github.com/eddiethedean/etlantic/blob/main/SECURITY.md)
   lists the current alpha line.
6. Run local gates:

   ```bash
   uv sync --locked
   uv run ruff check .
   uv run ruff format --check .
   uv run pytest -q -m "not sparkforge"
   uv run python scripts/check_docs.py
   uv run python scripts/check_agent_guidance.py
   uv run python scripts/check_release.py
   uv run python scripts/build_docs.py
   uv sync --locked --group sparkforge
   uv run pytest -q tests/sparkforge -m sparkforge
   ```

7. Review `scripts/check_release.py` output for **brand-new** PyPI names.
   PyPI has no empty-project UI — the first upload creates each name and
   counts against the new-project quota (`429 Too many new projects created`;
   defaults ~20 creates/hour). Release CI waits **10 minutes only between
   brand-new project creates**; existing projects upload immediately and
   already-published filenames are skipped. If the account is already
   rate-limited, wait for the rolling hour window before tagging/re-running.
8. Confirm repository secret `PYPI_API_TOKEN` is a **user-scoped** token
   (project-scoped tokens cannot create brand-new projects).
9. Prefer tagging only the current release (do not `git push --tags`).
10. If a prior tag’s publish job was cancelled mid-way, either re-run that
    release job until remaining packages land, or proceed to the next tag
    (new names will be created at the newer version).

## Tag and publish (0.13.0 example)

```bash
# On a clean main matching the intended commit:
git status
git pull --ff-only origin main

# Tag must match src/etlantic/_version.py (and every plugin package).
git tag -a v0.13.0 -m "ETLantic 0.13.0"
git push origin v0.13.0
```

GitHub Actions workflow
[release.yml](https://github.com/eddiethedean/etlantic/blob/main/.github/workflows/release.yml):

1. Runs the full checks matrix.
2. Verifies tag == core + all plugin versions.
3. Builds all nine wheels/sdists.
4. Smokes the core wheel (driver-free) **and** plugin discovery/import
   **before** any PyPI upload.
5. Publishes to PyPI: existing projects upload immediately; **10-minute**
   gaps only between brand-new project creates; skips files already present
   via `--check-url`; retries on transient 429s.
6. Creates the GitHub Release from `CHANGELOG.md` notes when publish succeeds.

## After PyPI succeeds

1. Verify `pip install etlantic==0.13.0` and plugin extras from a clean venv.
2. Create or confirm the GitHub Release for `v0.13.0`.
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

Plugins are separately installable and declare `etlantic>=X.Y.Z,<1.0`. A core
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
