# Documentation Status and Conventions

Prefer pages marked **Available in 0.21** and the Green path on the docs
home. For what ships in the current package, start with
[Capabilities](../01_GETTING_STARTED/CAPABILITIES.md)—not chapter length or
this legend.

## How to read a page

1. Read the page status label first (table below).
2. Treat **Available in 0.21** / **Shipped in 0.x** as current package
   behavior; treat **Future design** and Design Proposals as intended 1.0
   surfaces, not APIs to install against.
3. Treat **Experimental** as public but changeable without a major bump.
4. When a guide and a normative spec disagree, the spec wins (ODCS, DTCS,
   DPCS). Integration chapters explain ETLantic usage; they do not replace
   those specs.
5. Keep design layers distinct: contracts → `PipelinePlan` → plugin /
   compiled artifact → run result.

## Page status labels

| Page status | Meaning |
|---|---|
| Available in 0.21 | Tested against the current package |
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
- [Design Decisions](../11_DEVELOPMENT/DESIGN_DECISIONS.md)
- [Architecture Decisions](../11_DEVELOPMENT/ARCHITECTURE_DECISIONS.md)
