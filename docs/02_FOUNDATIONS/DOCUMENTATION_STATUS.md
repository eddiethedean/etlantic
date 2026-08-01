# Documentation Status and Conventions

Prefer pages marked **Available in 0.41** and the Green path on the docs
home. For what ships in the current package, start with
[Capabilities](../01_GETTING_STARTED/CAPABILITIES.md)—not chapter length or
this legend. Maintainer release evidence:
[Exit gate 0.39](../11_DEVELOPMENT/EXIT_GATE_0_39.md) and
[Migration 0.38 → 0.39](../11_DEVELOPMENT/MIGRATION_0_38_TO_0_39.md). Latest
completed documentation audit:
[Documentation audit 0.35](../11_DEVELOPMENT/DOCUMENTATION_AUDIT_0_35.md)
(use exit-gate / migration above for the current 0.39 gate).

## How to read a page

1. Read the page status label first (table below).
2. Treat **Available in 0.41** / **Shipped in 0.x** as current package
   behavior; treat **Future design** and Design Proposals as intended 0.x
   surfaces, not APIs to install against.
3. Treat **Experimental** as public but changeable without a major bump.
4. When a guide and a normative spec disagree, the spec wins ([ODCS](../03_DATA_CONTRACTS/ODCS.md), [DTCS](../04_TRANSFORMATIONS/DTCS.md),
   [DPCS](../05_PIPELINES/DPCS.md)). Integration chapters explain ETLantic usage; they do not replace
   those specs.
5. Keep design layers distinct: contracts → `PipelinePlan` → plugin /
   compiled artifact → run result.
6. Treat `PipelineDefinition`, `etlantic.pipeline/1`, functional builders,
   GUI catalogs/edit commands, and the FastAPI reference adapter as
   **Available in 0.41** (see
   [Programmatic authoring](../05_PIPELINES/PROGRAMMATIC_AUTHORING.md)).
   Historical design notes remain under Project → Archive.

## Page status labels

| Page status | Meaning |
|---|---|
| Available in 0.41 | Tested against the current package |
| Shipped in 0.x | Available since that milestone (still current) |
| Experimental | Public APIs that may change without a major version bump |
| Partially available | Shipped and future behavior are explicitly separated |
| Future design | Not a current API or installation guide |
| Normative specification | Contract requirements, not package behavior |
| Internal project plan | Maintainer sequencing and implementation notes |

## Conceptual stability labels

Documents also use these conceptual levels (usually in design or foundation
chapters):

| Label | Meaning |
|---|---|
| Foundational | A project boundary or principle expected to remain stable |
| Accepted design | A chosen API or architecture direction pending implementation |
| Proposed | A concrete surface that may change as implementation pressure appears |
| Normative | A requirement defined by a contract specification |
| Example | Illustrative code that expresses intended UX |

## See also

- [Capabilities](../01_GETTING_STARTED/CAPABILITIES.md) — current shipped surface
- [Roadmap](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md)
- [0.24 Programmatic Authoring Plan](../11_DEVELOPMENT/PROGRAMMATIC_AUTHORING_0_24.md)
- [Design Decisions](../11_DEVELOPMENT/DESIGN_DECISIONS.md)
- [Architecture Decisions](../11_DEVELOPMENT/ARCHITECTURE_DECISIONS.md)
