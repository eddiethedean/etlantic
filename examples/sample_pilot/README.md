# Sample pilot (production-shaped)

Clone-only example showing a production-shaped Polars pipeline with explicit
plugin trust, validation diagnostics, planning, and a durable run report.

## Run

```bash
pip install "etlantic[polars]"
uv run python examples/sample_pilot/run_pilot.py
```

The script writes only beneath its local sample workspace and uses secret
references rather than embedding secret values.

[Walkthrough](https://etlantic.readthedocs.io/en/latest/09_EXAMPLES/PRODUCTION_SAMPLE/) ·
[All examples](https://github.com/eddiethedean/etlantic/blob/main/examples/README.md)
