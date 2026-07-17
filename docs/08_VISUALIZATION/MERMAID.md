# Mermaid

> **Status: Available** for logical pipeline graphs via `Pipeline.to_mermaid()`.
> Graphviz DOT and HTML lineage exporters are also available via `etlantic.viz`
> (shipped in 0.9+).

ETLantic can generate a **Mermaid** flowchart from a pipeline's logical
graph. Mermaid renders in Markdown viewers, documentation sites, GitHub,
GitLab, and many IDEs.

## Purpose

- Inspect source → step → sink topology
- Embed pipeline structure in docs and PRs
- Confirm wiring before execution

## Generation (shipped)

```python
from pathlib import Path

diagram = CustomerPipeline.to_mermaid()
Path("customer_pipeline.mmd").write_text(diagram, encoding="utf-8")
print(diagram)
```

Only `Pipeline.to_mermaid()` and `etlantic.viz` exporters are available for
diagrams. Plan objects do not expose a Mermaid helper.

## Philosophy

Prefer generated diagrams over hand-maintained ones when the pipeline class is
the source of truth.

```text
Pipeline class
      │
      ▼
Logical graph
      │
      ▼
Mermaid text
```

## Limitations

- Output reflects the logical graph, not runtime schedules or engine-specific
  physical plans
- Advanced schedule overlays remain future design
- For Graphviz/HTML/lineage, see [Graphviz](GRAPHVIZ.md), [HTML](HTML.md), and
  [Lineage](LINEAGE.md)

## See also

- [First Pipeline](../01_GETTING_STARTED/FIRST_PIPELINE.md)
- [API Reference](../10_REFERENCE/API_REFERENCE.md)
- [Visualization overview](README.md)
