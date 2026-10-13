# Getting Started

**Start on the docs [Home](../README.md) green path**, then continue here in order:

1. Install with `pip install etlantic`
2. [Quickstart](QUICKSTART.md) — primary CLI path
3. [First Pipeline](FIRST_PIPELINE.md)
4. [Engine selection](ENGINE_SELECTION.md)
5. [Learning path](LEARNING_PATH.md)

Optional before install: [Compare](COMPARE.md) (“is this for me?”).
Capabilities teaser: [Capabilities](CAPABILITIES.md) (full matrix after first success).

After Ada/Grace success: [SDK 10 minutes](SDK_10_MINUTES.md) (secondary),
[FAQ](FAQ.md), [Troubleshooting](TROUBLESHOOTING.md), [Upgrade](UPGRADE.md),
[What's New in 0.59](WHATS_NEW_0_59.md) (release candidate), and
[What's New in 0.57](WHATS_NEW_0_57.md) (latest published Beta release).

Ignore **Project → Archive index** (and maintainer plans linked from it) until you contribute.

!!! tip "PyPI vs clone"
    Quickstart and First Pipeline are pip/CLI paths. Repository `examples/`
    need a git checkout — see
    [Installation](INSTALLATION.md).

!!! note "CLI run vs in-memory demos"
    The Quickstart binds assets to JSON files, so `python -m etlantic run` works without
    seeding. In-memory demos (`PipelineRuntime.memory.seed`) only share data
    inside one Python process—use
    [`examples/memory_customers.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/memory_customers.py)
    from a checkout for that path. Prefer the same `--profile` for validate,
    plan, and run (`development` by default when omitted).

ETLantic 0.57.x is the current published **Beta** line for documented
single-tenant pilots; 0.59.0 remains a candidate.
Prefer `import etlantic as etl` for application code after the CLI green path.
