# Mermaid

> **Status: Available in Pipelantic 0.6.0** for logical pipeline graphs via
> `Pipeline.to_mermaid()`. Graphviz/HTML exporters and plan-level Mermaid APIs
> are not shipped.

Pipelantic can generate a **Mermaid** flowchart from a pipeline's logical
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

Only `Pipeline.to_mermaid()` is available in 0.5. Plan objects do not expose a
Mermaid helper.

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
- Styling and advanced lineage views are future design
- For Graphviz/HTML, see Future Design → Visualization

## See also

- [First Pipeline](../01_GETTING_STARTED/FIRST_PIPELINE.md)
- [API Reference](../10_REFERENCE/API_REFERENCE.md)
- [Visualization overview](README.md)
