# CI Integration

> **Status: Available in ETLantic 0.18.0.**

Validate without executing transformation code and publish SARIF diagnostics.

## Development / local CI

```bash
etlantic validate package.pipeline:CustomerPipeline \
  --profile development --format sarif > etlantic.sarif
etlantic plan package.pipeline:CustomerPipeline \
  --profile development --format json > pipeline-plan.json
```

## Production profile (explicit allowlist)

The built-in `--profile production` template is intentionally empty and
**fail-closed**: it requires a non-empty `plugin_allowlist` and resolved
bindings. Do not use the bare name for CI until you supply a real profile.

Write a JSON profile (secret-free) and pass its path. Prefer the embedded
starter in [Capabilities → CI starter](../01_GETTING_STARTED/CAPABILITIES.md#ci-starter)
(not installed with the wheel):

```python
from etlantic import Profile, write_profile

write_profile(
    Profile(
        name="ci-production",
        dataframe_engine="local",
        security_domain="production",
        validation_policy="strict",
        plugin_allowlist={
            "local": None,
            # "etlantic-polars": "==0.18.0",
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
etlantic validate package.pipeline:CustomerPipeline \
  --profile profiles/ci-production.json --format sarif > etlantic.sarif
etlantic plan package.pipeline:CustomerPipeline \
  --profile profiles/ci-production.json --format json > pipeline-plan.json
```

`--profile` accepts a built-in name **or** a path to a `.json` profile file
loaded via `load_profile`.

Treat the plan as build metadata: it is secret-free, but may reveal pipeline
structure and resource names.

Recommended gates:

1. Pin ETLantic and official plugins to one tested release (`==0.18.0`).
2. Validate every changed pipeline with an explicit allowlisted profile.
3. Generate contracts and fail on unexpected diffs.
4. Upload SARIF through the CI platform's supported integration.
5. Compile orchestrator artifacts only from a valid plan.
6. Never resolve runtime secrets during validation or planning.

See [diagnostics](../10_REFERENCE/DIAGNOSTICS.md),
[security](../02_FOUNDATIONS/SECURITY.md),
[runtime configuration](../10_REFERENCE/RUNTIME_CONFIGURATION.md), and
[production profiles](PRODUCTION_PROFILES.md).
