# Controlled Pilot Walkthrough

ETLantic 0.21.0 is production/stable for the documented single-tenant reference
deployment. Use this walkthrough with pinned dependencies, explicit rollback,
and reviewed plans. Multi-tenant topology, compliance/SBOM/signing, and
advanced supply-chain controls remain adopter-owned; this is not an
unrestricted production-readiness claim.

## 1. Install a pinned release

Create an isolated Python 3.11–3.13 environment and pin core plus only the
plugins the pilot needs:

```bash
python -m pip install "etlantic==0.21.0" "etlantic-polars==0.21.0"
etlantic --help
```

See [Installation](../01_GETTING_STARTED/INSTALLATION.md) and the
[Compatibility Matrix](../10_REFERENCE/COMPATIBILITY.md).

## 2. Run the smallest pipeline

Work through the [Quickstart](../01_GETTING_STARTED/QUICKSTART.md), or run the
repository example from a source checkout:

```bash
python examples/quickstart.py
```

Confirm that the report succeeds and the two normalized customer rows are
printed.

## 3. Exercise file-backed execution in Python

Run the shipped JSON and CSV example:

```bash
python examples/file_storage.py
```

This example constructs a `PlanningContext`, registers file
`BindingDescriptor` values, and executes through Python. The CLI does not infer
those file descriptors from path strings. Review the
[File Storage Tutorial](FILE_STORAGE_TUTORIAL.md) before substituting pilot
paths.

## 4. Validate and plan without execution

Use an importable `module:Class` or `path.py:Class` target:

```bash
etlantic validate examples/quickstart.py:CustomerPipeline \
  --profile development --format json

etlantic plan examples/quickstart.py:CustomerPipeline \
  --profile development --format json > pipeline-plan.json
```

Review the plan's bindings, implementation selections, plugin versions,
security domain, and fingerprint. Planning does not resolve secrets or execute
transformation implementations.

## 5. Create an explicit production profile

The bare `production` profile is intentionally empty and fails closed. Generate
a reviewed JSON profile with a non-empty plugin allowlist and all logical
bindings:

```python
from etlantic import Profile, write_profile

write_profile(
    Profile(
        name="pilot-production",
        dataframe_engine="polars",
        security_domain="production",
        validation_policy="strict",
        plugin_allowlist={"etlantic-polars": "==0.21.0"},
        assets={
            "customer_source": "reviewed-source",
            "customer_sink": "reviewed-sink",
        },
        portable_transform_policy="require",
    ),
    "profiles/pilot-production.json",
)
```

Register concrete binding descriptors in the pilot application when the
selected providers are not already in the built-in or plugin registry. See
[Production Profiles](PRODUCTION_PROFILES.md).

## 6. Publish SARIF and retain the plan

```bash
etlantic validate examples/quickstart.py:CustomerPipeline \
  --profile profiles/pilot-production.json \
  --format sarif > etlantic.sarif

etlantic plan examples/quickstart.py:CustomerPipeline \
  --profile profiles/pilot-production.json \
  --format json > pipeline-plan.json
```

Upload `etlantic.sarif` through the CI platform's SARIF integration. Treat the
plan as controlled build metadata: it is secret-free, but exposes structure
and resource names. See [CI Integration](CI_INTEGRATION.md).

## 7. Persist run reports

Construct the Python runtime with a `FileReportStore`:

```python
from etlantic import PipelineRuntime, PlanningContext
from etlantic.reports.file_store import FileReportStore

profile_path = "profiles/pilot-production.json"
context = PlanningContext.create(profile=profile_path)
# Register any deployment-specific BindingDescriptor values on context.registry.
runtime = PipelineRuntime(reports=FileReportStore(".etlantic/reports"))
report = PilotPipeline.run(
    profile=profile_path,
    runtime=runtime,
    context=context,
)
```

Retain reports according to the pilot's access and retention policy. Compare
two runs with:

```bash
etlantic report compare RUN_BEFORE RUN_AFTER \
  --store .etlantic/reports --format json
```

See [Durable Run Reports](DURABLE_REPORTS.md).

## 8. Upgrade by regenerating

For every core or plugin upgrade:

1. Update all official ETLantic packages to the same minor release.
2. Recreate the isolated environment.
3. Re-run validation and conformance checks.
4. Regenerate contracts and the `PipelinePlan`; do not reuse a plan produced by
   another ETLantic or plugin version.
5. Review the new diagnostics, capability decisions, plugin versions, and plan
   fingerprint.
6. Run a non-production comparison before promotion.

Do not edit a serialized plan to make it fit a new release. Plans are
deterministic products of pipeline code, contracts, profiles, and installed
plugin capabilities.

Continue with [Capabilities and Limitations](../01_GETTING_STARTED/CAPABILITIES.md),
[Portable Compiler Matrix](../10_REFERENCE/PORTABLE_COMPILER_MATRIX.md), and
[Ops Pilot](OPS_PILOT.md).
