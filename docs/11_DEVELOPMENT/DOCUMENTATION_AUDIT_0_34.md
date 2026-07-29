# Documentation audit 0.34

> **Maintainer record.** Public-adoption documentation audit and follow-through
> for ETLantic **0.34.0**. Supersedes
> [Documentation audit 0.33](DOCUMENTATION_AUDIT_0_33.md) for current work.
> Historical audits remain under [Archive index](ARCHIVE_INDEX.md).

## Verdict

| Dimension | Score (1–10) | Note |
|---|---|---|
| Clarity | 7 | Dual CLI/SDK paths demoted; install truth explicit |
| Completeness | 7 | M6 ops cookbook + plugin protocol links; BYO secrets stub |
| Discoverability | 6 | Compare on Home/Learn; How-to nested under After first success |
| Learnability | 7 | Green path intact once install works |
| API documentation | 6 | Core hub OK; optional packages still README-canonical |
| Examples | 7 | Design-studies contradiction removed |
| Contributor experience | 7 | BUILDING_A_PLUGIN M6 protocol links |
| Professionalism | 7 | Beta honesty; Production readiness vs Unreleased clarified |

**Composite:** Fair-to-Good for day-0 adoption while PyPI lags at **0.33.0**;
Good once install from `main` (or published `0.34.0`) succeeds.

## Critical follow-through in this pass

1. **Install truth** — README, docs home, Installation, Quickstart lead with
   `git+…@main` until PyPI has `0.34.0`.
2. **Primary path** — CLI Quickstart sole day-0 path; SDK sample and
   `SDK_10_MINUTES` labeled post-Ada/Grace.
3. **Nav** — Compare promoted; How-to nested under Learn → After first success;
   Capabilities teaser on Home / Learning path.
4. **M6 ops** — Troubleshooting cookbook for `durable_audit`, report query,
   observability providers; deep links to Report / Observability pages.
5. **Plugin authors** — OBSERVABILITY / RUN_HISTORY / EVENT_CONSUMER linked from
   BUILDING_A_PLUGIN.
6. **Hygiene** — Examples README contradiction removed; SECURITY 0.33.x row;
   restamped 0.33/0.25 banners; Production readiness + What’s New honesty.
7. **Cross-links** — OPTIONAL_PACKAGES maturity callout; Engines →
   Troubleshooting; Medallantic M6 elevation; BYO secrets adapter stub;
   trimmed interchange-standard jargon from README architecture blurb.

## Residual / follow-ups

- Publish PyPI `0.34.0` (release ops; then flip install blocks to pin-first).
- Optional-package mkdocstrings hubs (still GitHub READMEs).
- Theme/type polish and further nav nesting (low leverage).
- Plan `0.34.1` narrative when Unreleased hardening ships (no tag required for
  docs wording alone).

## Cold-path checklist (manual)

1. Empty directory → install from `main` (or `etlantic==0.34.0` when published)
   → `init` → validate → run → Ada/Grace in `data/out.json`.
2. Required aha → restore → First Pipeline NamedRow lesson.
3. Open Home: Compare CTA + install truth + Capabilities teaser.
4. Open Troubleshooting: M6 ops cookbook present.
5. Open Building a Plugin: three M6 protocol links present.
6. Open Production readiness: pilot-slice honesty + Unreleased pointer.

## Related

- [Exit gate 0.34](EXIT_GATE_0_34.md)
- [Migration 0.33 → 0.34](MIGRATION_0_33_TO_0_34.md)
- [What’s new in 0.34](../01_GETTING_STARTED/WHATS_NEW_0_34.md)
- [Archive index](ARCHIVE_INDEX.md)
