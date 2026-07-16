# Documentation

!!! warning "Future design—not a Pipelantic 0.6 API guide"
    Graphviz, HTML, lineage exporters, and generated pipeline docs beyond
    Mermaid are not shipped in 0.5. For diagrams today, use
    `Pipeline.to_mermaid()`.


Pipelantic documentation should be generated from the same validated models
used for planning and execution.

Data contracts, transformation contracts, pipeline contracts, lineage,
diagnostics, diagrams, and runtime metadata should not be maintained in separate
handwritten systems. Pipelantic derives documentation from its canonical
models so the published material stays synchronized with the actual pipeline.

## Purpose

Generated documentation should help users:

- Understand pipeline purpose and ownership
- Inspect sources, steps, sinks, and subpipelines
- Review ODCS, DTCS, and DPCS relationships
- Explore lineage
- Diagnose validation problems
- Compare contract and pipeline versions
- Understand execution requirements
- Navigate large pipeline ecosystems

## Philosophy

Documentation is a projection of the validated model.

```text
Python Models and Contract Artifacts
                │
                ▼
        Canonical Object Models
                │
                ▼
            Validation
                │
                ▼
        Pipeline Plan and Lineage
                │
                ▼
      Documentation Generators
        ├── Markdown
        ├── HTML
        ├── Mermaid
        ├── Graphviz
        └── Interactive Views
```

Documentation generators consume structured metadata. They should not reinterpret
arbitrary source code or runtime logs as the canonical pipeline definition.

## Documentation Sources

Pipelantic documentation may combine information from:

- `DataContractModel` classes
- ODCS artifacts
- `Transformation` classes
- DTCS artifacts
- `Pipeline` classes
- DPCS artifacts
- Pipeline Plans
- Lineage models
- Validation diagnostics
- Plugin capability declarations
- Optional execution reports

Each source contributes a distinct layer of information.

## Logical and Runtime Documentation

Pipelantic should distinguish between two categories.

### Logical documentation

Describes the portable pipeline model:

- Contract identities and versions
- Data schemas
- Transformation interfaces
- Pipeline topology
- Public inputs and outputs
- Quality gates
- Failure semantics
- Lineage
- Execution requirements

Logical documentation should be identical across compatible execution
environments.

### Runtime documentation

Describes one profile, compilation target, or execution:

- Selected implementations
- Resolved plugin categories
- Target orchestrator
- Logical resource bindings
- Capability results
- Execution status
- Runtime diagnostics
- Record counts and timings

Runtime documentation supplements the logical model. It must not redefine it.

## Project Documentation

A complete project documentation site may include:

```text
documentation/
├── index.md
├── data-contracts/
├── transformations/
├── pipelines/
├── lineage/
├── diagnostics/
├── profiles/
└── plugins/
```

The exact output structure may vary by generator, but links and identities should
remain stable.

## Data Contract Documentation

Each published data contract page should include:

- Identifier
- Version
- Description
- Owner
- Domain
- Status
- Schema fields
- Types
- Required and nullable behavior
- Constraints
- Defaults
- Examples
- Compatibility information
- Upstream producers
- Downstream consumers

The page should reference the canonical ODCS artifact where available.

## Transformation Documentation

Each transformation page should include:

- Identifier
- Version
- Description
- Inputs
- Outputs
- Parameters
- Contract references
- Available implementation names
- Portability limitations
- Validation requirements
- Upstream and downstream usage

Documentation should describe the interface before implementation details.

## Pipeline Documentation

Each pipeline page should include:

- Pipeline identity
- Version
- Description
- Owner and domain
- Public interface
- Sources
- Steps
- Sinks
- Subpipelines
- Graph visualization
- Lineage
- Scheduling intent
- Execution requirements
- Quality gates
- Failure semantics
- Contract references
- Compatibility information

## Cross-Linking

Generated documentation should connect related artifacts.

Examples:

- A pipeline step links to its DTCS transformation.
- A transformation input links to its ODCS data contract.
- A sink links to the published output contract.
- A subpipeline links to its DPCS page.
- A contract page links to all known producers and consumers.
- A diagnostic links to the affected field, step, or pipeline.

Cross-linking turns isolated reference pages into a navigable system model.

## Lineage Documentation

Lineage pages should support both upstream and downstream exploration.

A user should be able to answer:

- Which sources contribute to this sink?
- Which transformations produce this dataset?
- Which pipelines consume this contract?
- What is affected by a breaking schema change?
- Which subpipeline boundaries does this data cross?

Lineage views may be rendered as Mermaid, Graphviz, SVG, HTML, or interactive
graphs.

## Diagnostics Documentation

Validation and planning diagnostics may be published as documentation reports.

A report should contain:

- Diagnostic code
- Severity
- Validation phase
- Affected object
- Message
- Suggested remediation
- Related locations
- Capability or compatibility context

Invalid pipelines should be clearly marked as invalid. A generated diagnostic
report should not be mistaken for a valid deployment artifact.

## Documentation API

Conceptually:

```python
CustomerPipeline.write_documentation(
    output="site/",
    format="html",
)
```

Project-level generation may include every discovered contract and pipeline:

```python
project.write_documentation(
    output="site/",
    formats={"markdown", "html", "mermaid"},
)
```

The final public API may differ, but generators should consume normalized
Pipelantic objects rather than private class internals.

## Documentation Profiles

Documentation generation may use a documentation profile.

Conceptually:

```python
DocumentationProfile(
    include_runtime_bindings=False,
    include_implementations=True,
    include_diagnostics=True,
    expand_subpipelines=False,
)
```

Documentation profiles control presentation and included views. They must not
alter contract or pipeline semantics.

## Markdown

Markdown output is useful for:

- Repository documentation
- GitHub and GitLab
- MkDocs
- Read the Docs
- Pull-request review
- Version-controlled references

Generated Markdown should use stable headings, anchors, and relative links.

## HTML

HTML output is useful for:

- Navigable sites
- Search
- Interactive lineage
- Offline reports
- Stakeholder review

HTML should remain accessible, secure, and reproducible.

## Diagrams

Documentation may embed generated diagrams.

Supported targets may include:

- Mermaid
- Graphviz DOT
- SVG
- PNG
- Interactive browser graphs

Every diagram should represent the same canonical graph and lineage semantics.

## Search and Indexing

Generated sites may create search indexes for:

- Pipeline names
- Contract identifiers
- Field names
- Transformation names
- Owners
- Domains
- Tags
- Diagnostic codes

Search data should derive from canonical metadata.

## Versioned Documentation

Published documentation should support multiple artifact versions.

Example:

```text
pipelines/
└── customer-pipeline/
    ├── 1.0.0/
    ├── 1.1.0/
    └── latest/
```

The `latest` alias is a publication convenience. It should not replace explicit
version identities in links or contract references.

## Compatibility Documentation

When multiple versions are available, Pipelantic may generate compatibility
reports describing:

- Compatible changes
- Conditional compatibility
- Breaking changes
- Migration paths
- Affected consumers
- Required transformation upgrades

These reports should use the compatibility models owned by ContractModel, DTCS,
and DPCS.

## Generated and Authored Content

Generated reference documentation may be combined with authored narrative
documentation.

For example:

```text
docs/
├── guides/               # Authored tutorials and explanations
└── reference/            # Generated contract and pipeline documentation
```

Authored content explains concepts and workflows.

Generated content describes the current project model.

Generated reference pages should never overwrite authored files unless the
output location is explicitly dedicated to generated material.

## Determinism

Documentation generation should be deterministic.

Equivalent source models should produce equivalent:

- File paths
- Headings
- Anchors
- Navigation ordering
- Cross-links
- Diagram identities
- Search records

Timestamps and environment-specific values should be optional.

## CI/CD

A recommended workflow is:

1. Validate contracts.
2. Validate pipelines.
3. Build Pipeline Plans.
4. Generate documentation.
5. Verify generated output is current.
6. Publish the site or artifacts.

CI may fail when committed generated documentation differs from regenerated
output.

## Incremental Generation

Large projects may generate only affected pages.

Changes to one data contract may require regeneration of:

- The data contract page
- Referencing transformations
- Consuming pipelines
- Relevant lineage views
- Compatibility reports

Incremental generation must produce the same result as a complete rebuild.

## Plugin Documentation

Plugins should expose metadata that can be documented automatically:

- Plugin name
- Version
- Category
- Supported SDK version
- Supported standards versions
- Capabilities
- Known limitations
- Configuration schema

This allows execution environments to be documented without copying plugin
details manually.

## Accessibility

Generated documentation should be accessible.

Requirements include:

- Semantic heading structure
- Keyboard navigation
- Descriptive link text
- Accessible tables
- Text alternatives for diagrams
- Sufficient color contrast
- Visible focus indicators
- Reduced-motion support
- Status indicators that do not rely on color alone

## Security and Privacy

Documentation generators must treat metadata and diagnostics as untrusted.

They should:

- Escape user-controlled content
- Prevent script injection
- Exclude secrets
- Redact sensitive values
- Avoid publishing internal physical bindings by default
- Support visibility controls
- Avoid embedding unsafe remote assets

Published documentation should reveal only the information intended for its
audience.

## Extensibility

Documentation plugins may add new output formats.

Examples include:

- Organization-specific portals
- Data catalogs
- Architecture repositories
- IDE indexes
- Search services
- Static-site generators

Extensions should consume public Pipelantic models and preserve stable
identities and references.

## Testing

Documentation generators should test:

- Deterministic output
- Stable links
- Complete cross-references
- Escaping and injection protection
- Accessibility
- Missing metadata handling
- Subpipeline expansion
- Multiple versions
- Large graphs
- Invalid model reports

Snapshot tests may be useful when combined with semantic assertions.

## Best Practices

- Generate reference documentation from validated models.
- Separate authored guides from generated reference pages.
- Cross-link contracts, transformations, pipelines, and lineage.
- Keep logical and runtime information distinct.
- Use stable identities in paths and anchors.
- Preserve deterministic output.
- Redact sensitive information.
- Publish explicit versions.
- Generate documentation in CI.

## Anti-Patterns

Avoid:

- Maintaining reference documentation manually.
- Generating documentation from execution logs alone.
- Mixing secrets into profile-aware pages.
- Using display labels as stable identities.
- Publishing unresolved contract references.
- Allowing generated files to overwrite authored guides.
- Creating different logical documentation for each execution backend.

## Key Principle

> Pipelantic documentation is generated from the same canonical contracts,
> Pipeline Plans, and lineage models used by validation and execution. It makes
> the system understandable without creating another source of truth that can
> drift from the implementation.

## Next Step

Continue with [OpenAPI for Pipelines](OPENAPI_FOR_PIPELINES.md) to explore a
machine-readable description of a pipeline's public interface.
