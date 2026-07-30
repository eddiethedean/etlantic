# Visualization

> **Available in 0.32:** Mermaid, Graphviz DOT, HTML lineage pages, and JSON
> lineage export via `etlantic.viz` and `python -m etlantic viz …` (first
> shipped in 0.9).

Visualization helps developers understand pipelines without reading every
implementation. Prefer diagrams generated from the typed model over hand-drawn
charts.

## Accessibility and browsers

- The docs site (Material for MkDocs) follows system light/dark preference and
  supports keyboard navigation for the primary chrome. Prefer the built-in
  theme toggle over custom CSS that removes focus outlines.
- Generated Mermaid / Graphviz / HTML lineage pages are developer aids: use a
  current Chromium, Firefox, or Safari build. Screen-reader coverage of SVG /
  canvas graphs is limited — treat `etlantic viz lineage` JSON (or the plan
  JSON) as the accessible source of truth when graphs are hard to perceive.
- Do not rely on color alone in custom HTML wrappers; keep text labels next to
  status colors.

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
