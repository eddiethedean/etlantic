# 5–10 Minute Quickstart

> **Status: Available in ETLantic 0.23.0.** Use `etlantic init` for the
> recommended CLI-first path with durable reports and declarative assets.

## 1. Install

ETLantic requires Python 3.11 or newer.

```bash
python -m pip install 'etlantic==0.23.0'
python -m etlantic --version
```

## 2. Initialize a project

```bash
mkdir my-pipeline && cd my-pipeline
etlantic init --with-toml
```

This creates `pipeline.py` (`SamplePipeline`), `profiles/development.json`,
sample `data/sample.json`, and `.etlantic/` workspace directories.

## 3. Validate, plan, and run

```bash
etlantic doctor --profile development
etlantic inspect pipeline.py:SamplePipeline
etlantic validate pipeline.py:SamplePipeline --profile development
etlantic plan pipeline.py:SamplePipeline --profile development
etlantic run pipeline.py:SamplePipeline --profile development
etlantic report list
```

No Python-side `runtime.memory.seed()` is required: the generated profile maps
assets to `json://data/...` paths.

### Success criteria

You should see a run status of `succeeded`. Inspect the written asset:

```bash
cat data/out.json
```

Expected shape (identity transform on sample rows):

```json
[
  {
    "id": 1,
    "name": "Ada"
  },
  {
    "id": 2,
    "name": "Grace"
  }
]
```

## 4. Python SDK path (optional)

For programmatic use, the same pipeline class works with the public SDK:

```python
from pipeline import SamplePipeline

report = SamplePipeline.validate(profile="development")
report.raise_for_errors()
SamplePipeline.plan(profile="development")
SamplePipeline.run(profile="development")
```

## Next steps

- [First Pipeline](FIRST_PIPELINE.md) — evolve the generated project (contracts,
  intentional errors, richer transforms)
- [Installation](INSTALLATION.md) — optional engine packages
- [What's New in 0.23](WHATS_NEW_0_23.md)

For an in-memory SDK demo from a checkout (not this Quickstart), see
[`examples/memory_customers.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/memory_customers.py).
