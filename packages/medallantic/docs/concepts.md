# Core concepts

## Medallantic is a facade

Medallantic expresses an opinionated pipeline architecture. It lowers that
architecture onto ordinary ETLantic concepts rather than maintaining a second
planner or runtime.

| Medallantic concept | ETLantic representation |
|---|---|
| Bronze input | `Extract` |
| Silver transformation | `Step` plus optional `Load` |
| Gold transformation | `Step` plus optional `Load` |
| Layer dependency | Typed graph edge / `OutputRef` |
| Layer quality threshold | Named validation-policy metadata |
| Output table | Profile asset plus `Load` |
| Write mode | `WriteIntent` |
| Initial/incremental/refresh | `RunIntent` |
| Run one/until/from | `RunSelection` |
| No-write debugging | `RunRequest.no_write` |
| Legacy execution result | `PipelineRunReport` |

Layer membership is carried by `AdaptationResult.layer_by_node`; it does not
become an enum in ETLantic core.

## Logical meaning and physical execution

A Medallantic definition describes pipeline intent. ETLantic validates and
plans it. Selected plugins realize it:

```text
Medallantic definition
        |
        v
ETLantic graph, policies, and plan
        |
        +--> Local / Polars / Pandas
        +--> SQL
        +--> PySpark
        +--> storage and observability providers
```

Choosing PySpark or SQL must not require a different public medallion model.
Backend-specific expressions may implement a transformation, but cannot define
the shared graph.

## Result references are not tables

An upstream result is a logical reference. Planning may keep it in memory,
preserve a lazy relation, cache it, checkpoint it, or materialize it. A table
is created only through an explicit load/publication decision.

This distinction prevents unnecessary round-trips and allows adjacent SQL or
Spark steps to remain in one optimized execution region.

## Quality is contract-backed

Medallantic owns useful layer defaults. ContractModel and ETLantic own portable
contract meaning, validation gates, typed accepted/rejected artifacts, and
normalized evidence.

The shipped portable rule DSL covers only semantics that can be defined
consistently. An engine-native rule remains an explicit implementation detail
with declared capability requirements.

## Capability promotion

A need discovered through Medallantic belongs in ETLantic when it:

- has the same meaning outside bronze/silver/gold pipelines
- is shared by multiple facades or plugins
- affects portable validation, planning, execution, evidence, or security
- can be named without medallion or engine terminology

Layer names, layer defaults, medallion naming/storage conventions, and
SparkForge migration behavior stay in Medallantic.
