# Learning path

> **Status: Available in ETLantic 0.34.0.** One ordered ladder from first
> install to week-2 CI. First paste still lives on the
> [docs home green path](../README.md).

## Week 1 — first success

| Step | Page | Done when |
|---|---|---|
| 1 | [Installation](INSTALLATION.md) | `python -m etlantic --version` prints `0.34.0` |
| 2 | [Quickstart](QUICKSTART.md) | `validate` / `run` succeed; Ada/Grace in `data/out.json`; aha failure observed |
| 3 | [First Pipeline](FIRST_PIPELINE.md) | Transform evolved; validate → plan → run still green |
| 4 | [Engine selection](ENGINE_SELECTION.md) | One engine tutorial completed (or stay on local) |

## Week 1 — deepen (pick one)

| Goal | Page |
|---|---|
| Builders / JSON authoring | [Programmatic authoring](../05_PIPELINES/PROGRAMMATIC_AUTHORING.md) |
| Profiles and production trust | [Profiles hub](../05_PIPELINES/PROFILES_HUB.md) |
| Portable transforms | [Portable transforms hub](../04_TRANSFORMATIONS/PORTABLE_HUB.md) |
| Day-2 security ops | [Security howto](SECURITY_HOWTO.md) |

## Week 2 — CI and pilot

| Step | Page | Done when |
|---|---|---|
| 1 | [Ops examples](OPS_EXAMPLES.md) | SARIF validate in CI; secrets via `SecretRef` |
| 2 | [Production profiles](../06_EXECUTION/PRODUCTION_PROFILES.md) | Non-empty `plugin_allowlist` for production mode |
| 3 | [CI integration](../06_EXECUTION/CI_INTEGRATION.md) | Validate gate on PRs |
| 4 | [Production readiness](../06_EXECUTION/PRODUCTION_READINESS.md) | Residual risks accepted for your pilot |

## Reference after first success

- [Current 0.34 Guide](CURRENT_VERSION.md) — task table
- [Cheatsheet](../10_REFERENCE/CHEATSHEET.md)
- [FAQ](FAQ.md) / [Troubleshooting](TROUBLESHOOTING.md) / [Upgrade](UPGRADE.md)
- Evaluators: [Evaluator Brief](EVALUATOR.md) → [Enterprise evaluation](ENTERPRISE_EVALUATION.md)
