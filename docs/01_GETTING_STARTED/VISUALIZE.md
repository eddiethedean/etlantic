# Visualize a pipeline

> **Status: Available in ETLantic 0.48.0.** After [Quickstart](QUICKSTART.md).

## Python

```python
from pathlib import Path

# SamplePipeline is the class from etlantic init (pipeline.py).
diagram = SamplePipeline.to_mermaid()
Path("pipeline.mmd").write_text(diagram, encoding="utf-8")
```

`to_mermaid()` uses the logical graph only. It does not plan or execute.

## CLI

From the Quickstart project:

```bash
python -m etlantic viz dot pipeline.py:SamplePipeline
python -m etlantic viz html pipeline.py:SamplePipeline -o lineage.html
python -m etlantic viz lineage pipeline.py:SamplePipeline --format json
```

`viz lineage` is read-only stdout. `viz html` always writes a file.
Details: [Mermaid](../08_VISUALIZATION/MERMAID.md) and
[CLI — viz](../10_REFERENCE/CLI.md#viz).
