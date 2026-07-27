# Security howto (day-2 ops)

> **Status: Available in ETLantic 0.25.0.** Operational checklist for pilots.
> Full threat model: [Security](../02_FOUNDATIONS/SECURITY.md).

## 1. Prefer `python -m etlantic`

Avoid PATH surprises on first machines:

```bash
python -m etlantic validate pipeline.py:SamplePipeline --profile development
```

## 2. Use named profiles and `security_mode`

```python
from etlantic import Profile

production = Profile(
    name="production",
    security_mode="production",
    security_domain="production",
    plugin_allowlist={
        "etlantic-polars": "==0.25.0",
        "etlantic-sql": "==0.25.0",
    },
)
```

Production fail-closed trust uses **`security_mode`** (not the profile name alone).
Empty allowlists fail closed in production.

## 3. Secrets are references only

- Author `SecretRef` metadata in contracts/profiles — never embed secret values
  in plans, reports, or docs.
- Resolve at runtime via env / file / optional keyring providers.
- See [Secrets Management](../06_EXECUTION/SECRETS_MANAGEMENT.md).

## 4. Validate in CI before write

Do **not** use the built-in `--profile production` name — its allowlist is empty
and fail-closed. Copy the canonical starter (clone) or paste the
[Capabilities CI JSON](CAPABILITIES.md#ci-starter):

```bash
cp docs/01_GETTING_STARTED/prod.example.json profiles/prod.json
# Review allowlist and assets, then:
python -m etlantic validate pipeline.py:SamplePipeline \
  --profile ./profiles/prod.json --format sarif
```

Pin core and plugins to the same minor (`==0.25.0`).

## 5. Know the shipped security diagnostics

Shipped `PMSEC*` codes today: `PMSEC050`, `PMSEC051`, `PMSEC060`. Allowlist and
trust failures use other families. See [Diagnostics](../10_REFERENCE/DIAGNOSTICS.md)
and [Security → Diagnostics](../02_FOUNDATIONS/SECURITY.md#diagnostics).

## Related

- [Profiles hub](../05_PIPELINES/PROFILES_HUB.md)
- [Production readiness](../06_EXECUTION/PRODUCTION_READINESS.md)
- [Evaluator Brief](EVALUATOR.md)
