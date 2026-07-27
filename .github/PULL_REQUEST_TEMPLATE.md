## Summary

<!-- What problem does this solve? -->

## Type of change

- [ ] Bug fix
- [ ] Feature
- [ ] Documentation
- [ ] Tests / CI
- [ ] Breaking public API (call out migration)

## Checklist

- [ ] Tests cover the change (or explain why not)
- [ ] Docs / changelog updated when user-visible
- [ ] No secrets or production data in the PR
- [ ] Compatibility impact considered (plans, plugins, contracts)
- [ ] Local checks: see [Contributing](docs/11_DEVELOPMENT/CONTRIBUTING.md) — docs-only PRs may use the minimal path; full PRs run `uv sync --locked` plus the CI-equivalent checklist (include `--group polars --group pandas --group sql --group pyspark --group datafusion` for `check_transform_compiler_drift.py`)

## Test plan

<!-- Commands you ran and expected results -->
