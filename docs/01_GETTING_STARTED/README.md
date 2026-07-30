# Getting Started

**Start on the docs [Home](https://etlantic.readthedocs.io/en/latest/) green path**, then continue here in order:

1. Install with `pip install etlantic`
2. [Quickstart](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/QUICKSTART/) — primary CLI path
3. [First Pipeline](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/FIRST_PIPELINE/)
4. [Engine selection](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/ENGINE_SELECTION/)
5. [Learning path](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/LEARNING_PATH/)

Optional before install: [Compare](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/COMPARE/) (“is this for me?”).
Capabilities teaser: [Capabilities](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/CAPABILITIES/) (full matrix after first success).

After Ada/Grace success: [SDK 10 minutes](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/SDK_10_MINUTES/) (secondary),
[FAQ](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/FAQ/), [Troubleshooting](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/TROUBLESHOOTING/), [Upgrade](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/UPGRADE/),
[What's New in 0.34](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/WHATS_NEW_0_34/).

Ignore **Maintainers** and **Standards** nav sections until you contribute.

!!! tip "PyPI vs clone"
    Quickstart and First Pipeline are pip/CLI paths. Repository `examples/`
    need a git checkout — see
    [Installation](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/INSTALLATION/).

!!! note "CLI run vs in-memory demos"
    The Quickstart binds assets to JSON files, so `python -m etlantic run` works without
    seeding. In-memory demos (`PipelineRuntime.memory.seed`) only share data
    inside one Python process—use
    [`examples/memory_customers.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/memory_customers.py)
    from a checkout for that path. Prefer the same `--profile` for validate,
    plan, and run (`development` by default when omitted).

ETLantic is currently a **Beta** release for documented single-tenant pilots.
Prefer `import etlantic as etl` for application code after the CLI green path.
