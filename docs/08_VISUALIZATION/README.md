# Visualization

> **Available in 0.32:** Mermaid, Graphviz DOT, HTML lineage pages, and JSON
> lineage export via `etlantic.viz` and `python -m etlantic viz …` (first
> shipped in 0.9).

Visualization helps developers understand pipelines without reading every
implementation. Prefer diagrams generated from the typed model over hand-drawn
charts.

## Shipped

- [Mermaid](https://etlantic.readthedocs.io/en/latest/08_VISUALIZATION/MERMAID/) — `Pipeline.to_mermaid()`
- [Graphviz](https://etlantic.readthedocs.io/en/latest/08_VISUALIZATION/GRAPHVIZ/) — DOT export (`etlantic.viz.graph_to_dot`)
- [HTML](https://etlantic.readthedocs.io/en/latest/08_VISUALIZATION/HTML/) — lineage HTML pages (`etlantic.viz.graph_to_html`)
- [Lineage](https://etlantic.readthedocs.io/en/latest/08_VISUALIZATION/LINEAGE/) — JSON lineage export (`etlantic.viz.lineage_export`)

## Future design

These pages describe intended richer surfaces beyond the 0.9 exporters:

- [Documentation](https://etlantic.readthedocs.io/en/latest/08_VISUALIZATION/DOCUMENTATION/)
- [Pipeline Interface](https://etlantic.readthedocs.io/en/latest/08_VISUALIZATION/OPENAPI_FOR_PIPELINES/)

See [Current Capabilities](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/CAPABILITIES/).
