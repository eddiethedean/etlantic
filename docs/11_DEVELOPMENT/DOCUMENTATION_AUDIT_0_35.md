# Documentation audit ledger — 0.35

> **Status: Internal project plan.** Tracks the post-0.35 documentation quality
> audit. Ownership map: [DOCUMENTATION_OWNERSHIP](DOCUMENTATION_OWNERSHIP.md).
> Release facts: [`docs/release-facts.json`](../release-facts.json).

| Finding | Owner / fix | Status |
|---|---|---|
| Mutable `/en/latest/` in release READMEs | Versioned `/en/v0.35.0/` links + RTD activation | Fixed in-repo; activate RTD tag in project UI |
| Current-facing 0.34 drift | ROADMAP, CAPABILITIES, EXIT_GATE, homepage, SUPPORT, VALIDATION | Fixed |
| Docs gate misses prior-minor “current” links | `check_docs.py` + release-facts | Fixed |
| Quickstart `UserWarning` on report metadata | Namespaced `etlantic.*` report keys | Fixed |
| SQL hello not paste-ready | Embedded script in `SQL_HELLO_PYPI.md` | Fixed |
| Interchange wheel/`examples/` mismatch | Embedded script + Expected output | Fixed |
| Runnable docs = py_compile only | Registry tiers (`syntax_checked`, `executed_in_ci`) | Fixed |
| Shallow optional-package API | Per-package pages under `api_optional/` | Fixed |
| Support policy duplication | Root SUPPORT canonical; docs pointer | Fixed |
| Status policy uneven | Frontmatter convention + nav status check | In progress |
| Navigation orphans | Hubs + ALL_CURRENT_GUIDES + orphan check | Fixed |
| Hero / contrast / reduced-motion | `etlantic.css` | Fixed |
| External link health | `scripts/check_external_links.py` | Fixed (internal fail; external report) |
| Immutable RTD tag 404 | Maintainer RTD Versions activation | Open (ops) |
| EthicalAds / custom domain | Out of repo | Noted — not actionable here |
| Independent third-party case study | Pilot evidence packet template only | Deferred (no fabricated study) |

## RTD activation reminder

1. Read the Docs → Versions → activate `v0.35.0`
2. Confirm `https://etlantic.readthedocs.io/en/v0.35.0/` returns 200
3. Keep `stable` = newest tag; `latest` = `main`
