# Getting Started

Continue from the docs home [green path](../README.md) — do not restart
onboarding here.

**Order:** [Installation](INSTALLATION.md) → [Quickstart](QUICKSTART.md) →
[First Pipeline](FIRST_PIPELINE.md) → [Engine selection](ENGINE_SELECTION.md)
→ [Learning path](LEARNING_PATH.md).

After Ada/Grace success: [FAQ](FAQ.md), [Troubleshooting](TROUBLESHOOTING.md),
[Upgrade](UPGRADE.md), [Capabilities](CAPABILITIES.md),
[What's New in 0.32](WHATS_NEW_0_32.md).

!!! note "CLI run vs in-memory demos"
    The Quickstart binds assets to JSON files, so `python -m etlantic run` works without
    seeding. In-memory demos (`PipelineRuntime.memory.seed`) only share data
    inside one Python process—use
    [`examples/memory_customers.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/memory_customers.py)
    from a checkout for that path. Prefer the same `--profile` for validate,
    plan, and run (`development` by default when omitted).

ETLantic **0.32.0** is a **Beta** (PyPI) release for documented single-tenant
pilots. Prefer `import etlantic as etl` for application code.
