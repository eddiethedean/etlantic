# Sample project layout

> **Status: Available in ETLantic 0.21.0.** A multi-file layout matching how
> teams usually organize contracts, transforms, and pipelines.

Runnable copy: `examples/sample_project/`.

```text
examples/sample_project/
  README.md
  contracts.py      # Data contracts
  transforms.py     # Transformation + local implementation
  pipeline.py       # Pipeline wiring
  run_local.py      # validate → plan → run
```

## Run

```bash
uv run python -m examples.sample_project.run_local
```

Expected: `succeeded` and curated customer records.

## Why this layout

- Contracts stay importable without pulling runtime seeds
- Transforms register implementations once
- Pipeline module is CLI-friendly (`pipeline.py:CustomerPipeline`)
- Runner owns seeding and execution

## Next

- [Quickstart](../01_GETTING_STARTED/QUICKSTART.md) (single-file version)
- [Ops examples](../01_GETTING_STARTED/OPS_EXAMPLES.md)
- [Engine selection](../01_GETTING_STARTED/ENGINE_SELECTION.md)
