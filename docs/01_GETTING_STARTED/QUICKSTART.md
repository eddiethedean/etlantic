# 5–10 Minute Quickstart

> **Status: Available in ETLantic 0.21.0.** Use `etlantic init` for the
> recommended CLI-first path with durable reports and declarative assets.

## 1. Install

ETLantic requires Python 3.11 or newer.

```bash
python -m pip install 'etlantic==0.21.0'
python -m etlantic --version
```

## 2. Initialize a project

```bash
mkdir my-pipeline && cd my-pipeline
etlantic init --with-toml
```

This creates `pipeline.py`, `profiles/development.json`, sample `data/`, and
`.etlantic/` workspace directories.

## 3. Validate, plan, and run (separate invocations)

```bash
etlantic doctor --profile development
etlantic inspect pipeline.py:SamplePipeline
etlantic validate pipeline.py:SamplePipeline --profile development
etlantic plan pipeline.py:SamplePipeline --profile development
etlantic run pipeline.py:SamplePipeline --profile development
etlantic report list
etlantic report show <run_id>
```

No Python-side `runtime.memory.seed()` is required: the generated profile maps
assets to `json://data/...` paths.

## 4. Python SDK path (optional)

For programmatic use, the same pipeline class works with the public SDK:

```python
from pipeline import SamplePipeline

report = SamplePipeline.validate(profile="development")
report.raise_for_errors()
SamplePipeline.plan(profile="development")
```

See [What's New in 0.21](WHATS_NEW_0_21.md) and the full
[Installation](INSTALLATION.md) guide for optional engine packages.

For the in-repo runnable companion, see
[`examples/quickstart.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/quickstart.py)
or run `uv run python examples/quickstart.py` from a checkout.
