# Lineage

!!! warning "Future design—not a Pipelantic 0.6 API guide"
    Graphviz, HTML, lineage exporters, and generated pipeline docs beyond
    Mermaid are not shipped in 0.5. For diagrams today, use
    `Pipeline.to_mermaid()`.


Data lineage describes how data moves through a Pipelantic pipeline, from its
original sources to its published outputs.

Because Pipelantic constructs a validated **Pipeline Plan** before execution,
lineage is derived from the pipeline's logical semantics rather than runtime
implementation details. This makes lineage deterministic, portable, and
independent of the execution backend.

## Purpose

Lineage answers questions such as:

- Where did this dataset originate?
- Which transformations produced it?
- Which pipelines consume it?
- What downstream systems depend on it?
- What contracts define its structure?
- What is affected if this contract changes?

## Philosophy

Lineage should be generated from the validated model.

```text
Python Pipeline
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
Lineage Graph
```

Execution may produce operational metadata, but it should never redefine the
logical lineage established by the Pipeline Plan.

## Lineage Model

Pipelantic derives lineage from:

- Sources
- Data contracts (ODCS)
- Transformations (DTCS)
- Pipeline graph (DPCS)
- Subpipeline interfaces
- Sinks

Conceptually:

```text
Source
  │
  ▼
Transformation A
  │
  ├──────────────┐
  ▼              ▼
Transformation B  Transformation C
  │              │
  └──────┬───────┘
         ▼
        Sink
```

## Types of Lineage

Pipelantic supports multiple logical views.

### Dataset Lineage

Shows relationships between datasets.

```text
raw.customers
      │
      ▼
customers
      │
      ▼
customer_metrics
```

### Transformation Lineage

Shows how transformations derive new datasets.

### Pipeline Lineage

Shows dependencies between pipelines and subpipelines.

### Contract Lineage

Shows how ODCS, DTCS, and DPCS contracts relate to one another.

## Subpipelines

Subpipelines preserve lineage boundaries.

Users may visualize:

- Collapsed lineage
- Expanded lineage
- Parent-child mappings

Both representations should describe the same semantics.

## Runtime Lineage

Execution plugins may emit runtime lineage events such as:

- Execution timestamps
- Row counts
- Materialization locations
- Execution identifiers

These enrich the lineage model but do not replace contractual lineage.

## Impact Analysis

Lineage enables impact analysis.

Examples include:

- Which pipelines consume a contract?
- Which sinks depend on a transformation?
- What breaks if a field changes?
- Which downstream systems require revalidation?

## Visualization

Lineage may be exported as:

- Mermaid
- Graphviz
- SVG
- HTML
- Interactive explorer

All visualizations should derive from the same Pipeline Plan.

## Best Practices

- Generate lineage from validated plans.
- Preserve stable node identities.
- Distinguish logical lineage from runtime history.
- Keep contract references explicit.
- Include subpipeline boundaries.

## Anti-Patterns

Avoid:

- Inferring lineage from execution logs alone.
- Coupling lineage to one orchestrator.
- Generating different lineage for different backends.
- Omitting contract references.

## Key Principle

> Lineage is a semantic property of a pipeline, not an implementation detail.
> Pipelantic derives lineage from the validated Pipeline Plan so every
> execution backend, visualization, and documentation tool shares the same
> consistent view of data provenance.

## Next Step

Continue with **MERMAID.md** to learn how Pipelantic renders lineage and
pipeline graphs using Mermaid diagrams.
