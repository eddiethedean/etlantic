# Visualization

> **Available in 0.32:** Mermaid, Graphviz DOT, HTML lineage pages, and JSON
> lineage export via `etlantic.viz` and `python -m etlantic viz …` (first
> shipped in 0.9).

Visualization helps developers understand pipelines without reading every
implementation. Prefer diagrams generated from the typed model over hand-drawn
charts.

## Shipped

- [Mermaid](MERMAID.md) — `Pipeline.to_mermaid()`
- [Graphviz](GRAPHVIZ.md) — DOT export (`etlantic.viz.graph_to_dot`)
- [HTML](HTML.md) — lineage HTML pages (`etlantic.viz.graph_to_html`)
- [Lineage](LINEAGE.md) — JSON lineage export (`etlantic.viz.lineage_export`)

## Future design

These pages describe intended richer surfaces beyond the 0.9 exporters:

- [Documentation](DOCUMENTATION.md)
- [Pipeline Interface](OPENAPI_FOR_PIPELINES.md)

See [Current Capabilities](../01_GETTING_STARTED/CAPABILITIES.md).
