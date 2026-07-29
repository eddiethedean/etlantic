# Lineage

!!! tip "Available in ETLantic 0.9"
    Use `etlantic.viz` or CLI `etlantic viz dot|html|lineage`.
    Mermaid remains available via `Pipeline.to_mermaid()`.



Data lineage describes how data moves through an ETLantic pipeline, from its
extracts to its published loads.

Because ETLantic constructs a validated **Pipeline Plan** before execution,
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

ETLantic derives lineage from:

- Extracts (logical source nodes)
- Data contracts ([ODCS](../03_DATA_CONTRACTS/ODCS.md))
- Transformations ([DTCS](../04_TRANSFORMATIONS/DTCS.md))
- Pipeline graph ([DPCS](../05_PIPELINES/DPCS.md))
- Subpipeline interfaces
- Loads (logical sink nodes)

Conceptually:

```text
Extract
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
        Load
```

## Types of Lineage

ETLantic supports multiple logical views.

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

Shipped lineage export (0.9):

```python
from etlantic.viz import lineage_export, logical_graph_to_ir, plan_to_ir

# From a pipeline class
doc = lineage_export(logical_graph_to_ir(CustomerPipeline.inspect()))

# From a resolved plan
plan = CustomerPipeline.plan(profile="development")
doc = lineage_export(plan_to_ir(plan))
# doc["schema"] == "etlantic.lineage/1"
```

CLI equivalent:

```bash
etlantic viz lineage path/to/pipeline.py:CustomerPipeline --format json
```

Related views:

- Mermaid via `Pipeline.to_mermaid()`
- Graphviz DOT via `etlantic.viz.graph_to_dot`
- HTML via `etlantic.viz.graph_to_html`

All of these derive from the same logical graph / plan IR.

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
> ETLantic derives lineage from the validated Pipeline Plan so every
> execution backend, visualization, and documentation tool shares the same
> consistent view of data provenance.

## Next Step

Continue with **MERMAID.md** to learn how ETLantic renders lineage and
pipeline graphs using Mermaid diagrams.
