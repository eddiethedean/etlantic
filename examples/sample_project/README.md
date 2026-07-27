# Sample multi-file project

Clone-only demo (not in the PyPI wheel). From the repository root after
`uv sync --locked`:

```bash
uv run python -m examples.sample_project.run_local
```

**Expected:** prints a `succeeded` run status and curated customer rows
(normalized full names), same story as `examples/memory_customers.py` split
across modules.

| Module | Role |
|---|---|
| `contracts.py` | `RawCustomer` / `Customer` data contracts |
| `transforms.py` | `NormalizeCustomers` transformation + local impl |
| `pipeline.py` | `CustomerPipeline` extract → step → load |
| `run_local.py` | Bindings + `PipelineRuntime` seed and run |

Docs walkthrough:
[Sample project](../docs/09_EXAMPLES/SAMPLE_PROJECT.md).
