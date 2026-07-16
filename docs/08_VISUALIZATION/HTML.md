# HTML

!!! warning "Future design—not a Pipelantic 0.6 API guide"
    Graphviz, HTML, lineage exporters, and generated pipeline docs beyond
    Mermaid are not shipped in 0.5. For diagrams today, use
    `Pipeline.to_mermaid()`.


Pipelantic can generate **HTML documentation** from a validated Pipeline Plan.

HTML output combines pipeline structure, contracts, lineage, diagnostics, and
visualizations into a navigable document that can be viewed locally, published
to a documentation site, attached to a release, or embedded in a broader data
platform.

Like every Pipelantic visualization, HTML documentation is derived from the
canonical Pipeline Plan rather than maintained separately.

## Purpose

HTML generation supports:

- Self-contained pipeline documentation
- Interactive pipeline graphs
- Contract reference pages
- Lineage exploration
- Planning diagnostics
- Architecture reviews
- Release artifacts
- Offline documentation

## Philosophy

Documentation should be generated from the validated model.

```text
Pipeline
    │
    ▼
Validation
    │
    ▼
Planning
    │
    ▼
Pipeline Plan (IR)
    │
    ▼
HTML Generator
    │
    ▼
Navigable Documentation
```

The HTML output is a view of the pipeline, not a separate source of truth.

## Why HTML?

HTML provides:

- Broad browser support
- Rich navigation
- Searchable content
- Interactive diagrams
- Portable offline viewing
- Easy publishing
- Flexible styling

It is especially useful for stakeholders who do not work directly with Python
or contract files.

## Generated Content

An HTML documentation bundle may include:

- Pipeline overview
- Public inputs and outputs
- Sources
- Steps
- Sinks
- Subpipelines
- ODCS references
- DTCS references
- DPCS metadata
- Lineage
- Mermaid or Graphviz diagrams
- Validation diagnostics
- Execution requirements
- Plugin capability requirements

## Pipeline Overview

The overview page should summarize:

- Pipeline name
- Identifier
- Version
- Description
- Owner
- Domain
- Status
- Tags
- Public interface
- Referenced contracts

## Step Pages

Each pipeline step may receive a dedicated page containing:

- Stable step identity
- Transformation reference
- Inputs
- Outputs
- Parameters
- Dependencies
- Lineage
- Validation requirements
- Selected implementation, when rendering a planned profile

Logical documentation should remain distinct from runtime-specific details.

## Contract Pages

HTML output may include generated documentation for:

- ODCS data contracts
- DTCS transformation contracts
- DPCS pipeline contracts

References between pages should be navigable.

For example:

```text
Pipeline Step
    │
    ├── Data Contract
    └── Transformation Contract
```

## Lineage Explorer

HTML documentation may provide an interactive lineage view that supports:

- Expanding and collapsing subpipelines
- Filtering by source or sink
- Inspecting contract references
- Tracing upstream dependencies
- Tracing downstream consumers
- Highlighting impact paths

The interactive view must preserve the same lineage semantics as static
Mermaid and Graphviz exports.

## Static and Interactive Modes

Pipelantic may support two HTML output modes.

### Static

Produces a simple documentation site with no application server.

Best for:

- CI artifacts
- GitHub Pages
- Offline review
- Documentation hosting

### Interactive

Adds browser-side interaction such as:

- Search
- Filtering
- Expandable graphs
- Detail panels
- Diagnostics inspection

Interactive behavior should enhance presentation without redefining pipeline
semantics.

## Self-Contained Output

A self-contained HTML file may embed:

- Styles
- Scripts
- SVG diagrams
- Contract metadata
- Navigation data

This format is useful for sharing one portable file.

Conceptually:

```python
plan.write_html(
    "customer-pipeline.html",
    self_contained=True,
)
```

## Documentation Site Output

For larger projects, Pipelantic may generate a directory:

```text
site/
├── index.html
├── pipelines/
│   └── customer-pipeline.html
├── transformations/
│   └── normalize-customers.html
├── data-contracts/
│   └── customer.html
├── lineage/
│   └── customer-pipeline.html
└── assets/
```

This structure supports multiple pipelines and reusable contracts.

## Generation API

Conceptually:

```python
html = plan.to_html()
```

or:

```python
plan.write_html(
    "docs/generated/customer-pipeline.html",
)
```

Project-level generation may produce a complete site:

```python
project.write_documentation(
    output="site/",
    format="html",
)
```

The exact API may evolve, but all HTML output should derive from validated
Pipelantic artifacts.

## Profile-Aware Documentation

HTML documentation may optionally include information from an execution
profile, such as:

- Selected implementations
- Resolved plugin types
- Capability results
- Logical resource bindings
- Compilation target

Secrets, credentials, and sensitive physical values must not be embedded.

A profile-aware document should clearly distinguish:

- Portable pipeline semantics
- Environment-specific planning information
- Runtime observations

## Validation Diagnostics

HTML output may present structured diagnostics grouped by:

- Severity
- Validation phase
- Pipeline
- Step
- Contract
- Source location

Diagnostics may include remediation guidance and links to affected objects.

A document generated from an invalid pipeline should be explicitly marked as a
diagnostic report rather than presented as a valid execution artifact.

## Execution Reports

Runtime plugins may generate HTML execution reports containing:

- Run identity
- Start and end times
- Step status
- Retry history
- Record counts
- Validation results
- Runtime lineage
- Diagnostics

Execution reports supplement model documentation.

They must not replace the canonical pipeline documentation.

HTML execution reports are rendered from the canonical
`PipelineRunReport`; runtime plugins should not invent incompatible report
schemas. See [Run Reports](../06_EXECUTION/RUN_REPORTS.md).

## Accessibility

Generated HTML should follow accessible web practices.

Requirements should include:

- Semantic headings
- Keyboard navigation
- Sufficient contrast
- Text alternatives for diagrams
- Screen-reader-friendly tables
- Focus visibility
- Reduced-motion support
- No color-only status indicators

Accessible documentation is part of the developer experience.

## Security

HTML generators must treat contract metadata and diagnostics as untrusted input.

Generators should:

- Escape user-provided text
- Prevent script injection
- Avoid embedding secrets
- Redact sensitive diagnostic values
- Restrict unsafe external resources
- Support Content Security Policy where practical

Self-contained output should not silently include remote scripts.

## Styling and Themes

Pipelantic may provide standard themes such as:

- Light
- Dark
- Automatic system preference
- Print-friendly

Themes affect presentation only.

Generated semantic structure and identifiers should remain stable.

## Determinism

Equivalent Pipeline Plans should produce semantically equivalent HTML output.

Generators should preserve stable:

- Page paths
- Anchor identifiers
- Node identities
- Navigation ordering
- Contract links

Build timestamps and runtime-generated identifiers should be optional so
reproducible documentation builds remain possible.

## Search

Generated sites may include client-side search across:

- Pipelines
- Steps
- Contracts
- Fields
- Owners
- Tags
- Diagnostics

Search indexes should be derived from the same canonical metadata used to
generate pages.

## CI/CD

A typical automated workflow is:

1. Validate contracts.
2. Validate pipelines.
3. Build Pipeline Plans.
4. Generate HTML documentation.
5. Check deterministic output.
6. Publish the site or attach an artifact.

Documentation generation should fail when required references cannot be
resolved.

## Relationship to Mermaid and Graphviz

HTML may embed multiple visualization formats.

### Mermaid

Useful for lightweight, browser-rendered diagrams.

### Graphviz SVG

Useful for complex, pre-rendered diagrams.

### Interactive graph

Useful for exploration and filtering.

All three should depict the same Pipeline Plan semantics.

## Best Practices

- Generate HTML from validated Pipeline Plans.
- Keep logical and runtime information clearly separated.
- Use stable URLs and anchors.
- Provide accessible text alternatives for diagrams.
- Escape all user-controlled metadata.
- Redact sensitive values.
- Support self-contained and site modes.
- Keep generated output deterministic.

## Anti-Patterns

Avoid:

- Maintaining HTML documentation manually.
- Generating pages directly from runtime logs.
- Embedding secrets or credentials.
- Allowing scripts in contract descriptions.
- Using profile-specific details as the canonical pipeline definition.
- Producing HTML that cannot be regenerated from source models.

## Key Principle

> HTML documentation is a navigable projection of Pipelantic's canonical
> contracts and Pipeline Plan. It makes pipeline semantics accessible to humans
> without creating another definition that can drift from the source of truth.

## Next Step

Continue with [Documentation](DOCUMENTATION.md) to learn how diagrams, contracts,
lineage, and diagnostics become a navigable documentation site.
