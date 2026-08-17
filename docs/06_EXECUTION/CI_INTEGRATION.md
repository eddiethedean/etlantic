# CI Integration

> **Status: Available in ETLantic 0.47.0.**

Validate without executing transformation code and publish SARIF diagnostics.

## Development / local CI

```bash
python -m etlantic validate package.pipeline:CustomerPipeline \
  --profile development --format sarif > etlantic.sarif
python -m etlantic plan package.pipeline:CustomerPipeline \
  --profile development --format json > pipeline-plan.json
```

## Production profile (explicit allowlist)

The built-in `--profile production` template is intentionally empty and
**fail-closed**: it requires a non-empty `plugin_allowlist` and resolved
bindings. Do not use the bare name for CI until you supply a real profile.

Write a JSON profile (secret-free) and pass its path. Prefer
[prod.example.json](../01_GETTING_STARTED/prod.example.json) or the embedded
starter in [Capabilities → CI starter](../01_GETTING_STARTED/CAPABILITIES.md#ci-starter)
(not installed with the wheel). Fail-closed trust requires
`security_mode="production"` (not the profile name or `security_domain` alone):

```python
from etlantic import Profile
from etlantic.profile import write_profile

write_profile(
    Profile(
        name="ci-production",
        dataframe_engine="local",
        security_mode="production",  # required for fail-closed trust
        security_domain="production",
        validation_policy="strict",
        plugin_allowlist={
            "local": None,
            # "etlantic-polars": "==0.47.0",
        },
        assets={
            # Logical binding name → provider key or descriptor name
            # "customer_source": "json",
        },
    ),
    "profiles/ci-production.json",
)
```

```bash
python -m etlantic validate package.pipeline:CustomerPipeline \
  --profile profiles/ci-production.json --format sarif > etlantic.sarif
python -m etlantic plan package.pipeline:CustomerPipeline \
  --profile profiles/ci-production.json --format json > pipeline-plan.json
```

`--profile` accepts a built-in name **or** a path to a `.json` profile file
loaded via `load_profile`.

Treat the plan as build metadata: it is secret-free, but may reveal pipeline
structure and resource names.

## GitHub Actions (copy-paste)

Validate as SARIF and emit a plan on every pull request. Adjust the pipeline
target, profile path, and package pins for your repository.

```yaml
name: ETLantic CI
on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read
  security-events: write  # required to upload SARIF

jobs:
  validate-and-plan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7

      - uses: actions/setup-python@v7
        with:
          python-version: "3.11"

      - name: Install ETLantic
        run: |
          python -m pip install --upgrade pip
          python -m pip install 'etlantic==0.47.0'
          # Add matching plugins when the pipeline needs them, e.g.:
          # python -m pip install 'etlantic-polars==0.47.0'

      - name: Validate (SARIF)
        run: |
          python -m etlantic validate pipeline.py:SamplePipeline \
            --profile development \
            --format sarif > etlantic.sarif

      - name: Upload SARIF
        uses: github/codeql-action/upload-sarif@v4
        with:
          sarif_file: etlantic.sarif
        # Skip upload forks without security-events permission:
        # if: github.event.pull_request.head.repo.full_name == github.repository

      - name: Plan
        run: |
          python -m etlantic plan pipeline.py:SamplePipeline \
            --profile development \
            --format json > pipeline-plan.json

      - name: Retain plan artifact
        uses: actions/upload-artifact@v7
        with:
          name: pipeline-plan
          path: pipeline-plan.json
```

For production profiles in CI, pass a checked-in allowlisted JSON path (see
above) instead of bare `production`. Never resolve runtime secrets during
validate or plan.

Recommended gates:

1. Pin ETLantic and official plugins to one tested release (`==0.47.0`).
2. Validate every changed pipeline with an explicit allowlisted profile.
3. Generate contracts and fail on unexpected diffs.
4. Upload SARIF through the CI platform's supported integration.
5. Compile orchestrator artifacts only from a valid plan.
6. Never resolve runtime secrets during validation or planning.

See [diagnostics](../10_REFERENCE/DIAGNOSTICS.md),
[security](../02_FOUNDATIONS/SECURITY.md),
[runtime configuration](../10_REFERENCE/RUNTIME_CONFIGURATION.md), and
[production profiles](PRODUCTION_PROFILES.md).
