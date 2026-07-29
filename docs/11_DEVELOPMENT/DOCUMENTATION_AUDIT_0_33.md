# Documentation audit 0.33

> **Maintainer record.** Adoption-focused audit follow-through for ETLantic
> **0.33.0**. Supersedes [Documentation audit 0.32](DOCUMENTATION_AUDIT_0_32.md)
> for current work. Historical audits remain under
> [Archive index](ARCHIVE_INDEX.md).

## Verdict

| Dimension | Score (1–10) | Note |
|---|---|---|
| Clarity | 6 | Green path strong; Gate jargon reduced in Capabilities/FAQ |
| Completeness | 7 | PyPI SQL hello + secrets decision tree + plugin manifests |
| Discoverability | 6 | Learn ladder clear; Evaluate collapsed; design studies deleted |
| Learnability | 6 | Unified-diff aha; Polars/Pandas/SQL PyPI paths |
| API documentation | 5 | Top-10 cookbook + diagnostics links; optional pkgs still READMEs |
| Examples | 6 | Production sample + emptied design studies removed |
| Contributor experience | 7 | Setup/checklists unchanged |
| Professionalism | 7 | Migration labels, MERGE, currency stamps fixed |

**Composite:** Good (improving from Fair), with residual optional-package API
depth and enterprise control→evidence polish still open.

## Repository-wide follow-through (2026-07-29)

A second pass covered all Markdown surfaces in the repository, not only the
MkDocs navigation:

- synchronized official package README pins and release descriptions to 0.33
- removed or relabeled Python examples for APIs that are not public
- aligned SQL documentation with the SQLite/PostgreSQL Tier A matrix
- updated Medallantic package docs for callable execution, quality rules, live
  SparkForge/SQL builder bridges, and M5 parity
- corrected local links outside the MkDocs tree and normalized ETLantic naming
- extended `check_docs.py` to verify package pins and local Markdown targets

The pass also re-ran strict site, runnable-example, release-readiness, agent
guidance, and surface-inventory gates.

## Critical fixes landed in this pass

1. **Migration labels** — adopter pages say **0.32 → 0.33** (not 0.33 → 0.33);
   UPGRADE milestone/Don’t column corrected; `check_docs` guards added.
2. **SQL MERGE** — INSTALLATION / SQL tutorials match PostgreSQL
   `sql_merge=True` / SQLite fail-closed.
3. **Currency stamps** — SECURITY, SURFACE_INVENTORY, WIRE_SCHEMA,
   Medallantic, STRUCTURED_STREAMING, PROFILES_HUB aligned to 0.33.
4. **Secrets decision tree** — normative page; CONFIGURATION / ENVIRONMENT
   future stubs demoted.
5. **Profiles field list** — matches Configuration today (no logging /
   checkpoint overclaim).
6. **Plugin manifests** — BUILDING_A_PLUGIN documents
   `etlantic-plugin-manifest.json` + digests / `PMPLUG411`.
7. **Capabilities / FAQ** — Today brief + residual appendix; FAQ slimmed.
8. **Quickstart aha** — unified diff against scaffold.
9. **README engines** — clone / experimental caveats.
10. **PyPI SQL hello** + Troubleshooting PyPI-first remediations.
11. **Design-study shells deleted**; production sample added.
12. **API top-10 cookbook** table with diagnostic links.
13. **Experimental surfaces** one-pager; nav IA cleanup.

## Residual / follow-ups

- Optional-package API hubs inside MkDocs (still GitHub READMEs).
- Enterprise control→evidence one-pager.
- Contributor Spark/Delta live lab guide.
- Ops runbook narrative by every diagnostic family (catalog exists).

## Cold-path checklist (manual)

1. Empty directory → `pip install etlantic==0.33.0` → `init` → validate → run.
2. Required aha unified diff → `PMPIPE210` → restore.
3. `pip install etlantic[polars]==0.33.0` → Polars tutorial → validate → run.
4. Paste [SQL hello](../06_EXECUTION/SQL_HELLO_PYPI.md) → `succeeded`.
5. Open Upgrade: Migration **0.32 → 0.33** labels; no “0.33 → 0.33”.
6. Open INSTALLATION SQL: PostgreSQL merge advertised; SQLite fail-closed.
7. Open Building a Plugin: manifest + digest section present.

## Related

- [Exit gate 0.33](EXIT_GATE_0_33.md)
- [Migration 0.32 → 0.33](MIGRATION_0_32_TO_0_33.md)
- [Archive index](ARCHIVE_INDEX.md)
