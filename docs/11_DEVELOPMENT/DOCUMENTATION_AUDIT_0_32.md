# Documentation audit 0.32

> **Maintainer record.** Adoption-focused audit against ETLantic **0.32.0**.
> Supersedes the 0.25 documentation / adoption audits for current work.
> Historical audits remain under [Archive index](ARCHIVE_INDEX.md).

## Verdict

| Dimension | Score (1–10) | Note |
|---|---|---|
| Clarity | 5 → improving | Positioning strong; Gate jargon still dense in Capabilities |
| Completeness | 6 | Breadth high; second-hour PyPI path was the gap |
| Discoverability | 5 → improving | Green path + Learning path + Reference API-first nav |
| Learnability | 5 → improving | PyPI Polars/Pandas tutorials; SQL/PySpark clone-assisted |
| API documentation | 4 → improving | Added provisional `etlantic.quality` page; optional packages still GitHub READMEs |
| Examples | 4 → improving | Init→Polars path without clone |
| Contributor experience | 7 | Setup/checklists remain strong |
| Professionalism | 6 → improving | 0.32 currency pass on security/inventories/enterprise |

**Composite:** Fair, with targeted fixes landed for the Critical adoption blockers.

## Critical fixes landed in this pass

1. **Cookbook Polars recipe** — no longer claims engine flip alone works on the
   `init` scaffold; requires a `"polars"` implementation.
2. **PyPI Polars / Pandas tutorials** — add engine to an `init` project without
   cloning; clone demos retained as optional companions.
3. **Enterprise evaluation** — Medallantic status aligned to 0.29–0.32; upgrade
   link points at Migration 0.31 → 0.32.
4. **0.32 currency** — SECURITY, surface inventory, wire ranges, compiler
   matrix, production readiness, execution README, Plugin SDK overview no
   longer advertise 0.28/0.31 as the current envelope.
5. **Plugin allowlist semantics** — single normative story:
   discover → evaluate → authorize → load; install is the trust boundary;
   allowlist is selection, not a sandbox.
6. **Canonical aha** — Quickstart and First Pipeline share one complete
   `Other` / `PMPIPE210` paste.
7. **Navigation** — Learning path on docs home; API hub first in Reference;
   Maintainers nav pruned to current + archive; Release notes collapse older
   What’s New under Earlier releases.
8. **`etlantic.quality` API page** — provisional mkdocstrings surface.

## Residual / follow-ups

- Split Capabilities into short adopter brief + residual appendix (content still
  long).
- Optional-package API hubs inside MkDocs (or keep honest core-only disclaimer —
  already stated in Optional Packages).
- Enterprise control→evidence one-pager.
- Contributor Spark/Delta live lab guide.
- Ghost Future config pages remain buildable (`CONFIGURATION.md`,
  `ENVIRONMENT_VARIABLES.md`) with hard deprecation banners — prefer
  Configuration today.
- Aspirational `09_EXAMPLES/*` excluded from the site still exist on GitHub.

## Cold-path checklist (manual)

1. Empty directory → `pip install etlantic==0.32.0` → `init` → validate → run.
2. Install `etlantic[polars]==0.32.0` → add Polars implementation → set
   `dataframe_engine` → validate → run (**no clone**).
3. Open Enterprise evaluation: Medallantic paragraph and upgrade link match
   0.32 truth.
4. Open Security: allowlist wording matches Architecture and API Plan/runtime.

## Related

- [Exit gate 0.32](EXIT_GATE_0_32.md)
- [Migration 0.31 → 0.32](MIGRATION_0_31_TO_0_32.md)
- [Archive index](ARCHIVE_INDEX.md)
