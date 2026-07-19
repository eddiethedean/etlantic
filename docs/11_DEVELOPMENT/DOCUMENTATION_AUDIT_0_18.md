> Status: Maintained audit for ETLantic 0.18.0 documentation adoption cut
> (updated after public-adoption remediation).

# Critical Documentation Audit — ETLantic 0.18

This audit records the documentation condition after the 0.18 adoption
remediation **and** the follow-up adoption-hygiene pass. It succeeds
[DOCUMENTATION_AUDIT_0_17.md](DOCUMENTATION_AUDIT_0_17.md) as the maintained
release artifact. Reassess when release posture or public package behavior
changes.

## Executive Summary

- **Overall documentation quality: Fair → Good (after remediation).**
- **Would I personally trust this project based on the documentation?** Yes,
  for evaluation and documented single-tenant reference deployments, after
  reading Capabilities, Evaluator, and Production readiness.
- **Why?** Critical factual errors (impossible plugin pin, Sink/Source as
  current vocabulary, unbannered storage catalogs) are fixed; green path
  next-steps point at Engine selection; design studies are stubs; Evaluate
  section separates diligence from Learn; Upgrade hub and Storage today exist.

Earlier self-rating of “Good” before this pass was **too generous** against
FastAPI/Pydantic/dbt onboarding craft. Honesty was already strong; hygiene
was not.

## Remediated in this cut

1. `OPTIONAL_PACKAGES.md` pin corrected to `etlantic>=0.18.0,<0.19`
2. `PIPELINE.md` / `STEPS.md` / Glossary use Extract/Load authoring vocabulary
3. `STORAGE_PLUGINS.md` Future stub + new `STORAGE_TODAY.md`
4. Green path: Install → Quickstart → First Pipeline → **Engine selection**
5. `examples/quickstart.py` matches validate → plan → run
6. Core-first `INSTALLATION.md` with JVM note for PySpark
7. CLI memory/profile callouts on Quickstart and First Pipeline
8. Stale 0.17 success banners refreshed on key adopter pages
9. README/docs home lead with bounded **stable** claim (not orphan “production”)
10. Design studies stubbed (no copy-paste deprecated APIs)
11. Learn nav slimmed; **Evaluate** section added; Design Proposals remain labeled not shipped
12. Upgrade hub, Ops examples, Portable failure cookbook, Gate A FAQ
13. API reference split (hub + Authoring / Plan-runtime / Protocols)
14. Plugin SDK overview is shipped-first with Future appendix
15. Performance pages framed for 0.18; 0.10 baselines labeled historical
16. Multi-file `examples/sample_project/`
17. Root `__init__.py` docstring no longer opens on “0.11 adds…”

## Remaining debt (not blocking 0.18 docs gate)

- Refresh quantitative performance baselines on current 0.18.x
- Further demote Design Proposals (search-only / collapsed theme)
- Versioned docs site per release
- Broader typed Returns on public Pipeline methods (`Any` cleanup is code)

## Release documentation gate checklist

Before tagging a minor/patch docs cut:

- [ ] Grep adopter pages for impossible pins (`<0.18` style empty ranges)
- [ ] Grep for teaching `Source`/`Sink` as current (exclude migration/deprecated pages)
- [ ] Confirm green path step 4 is Engine selection (not Capabilities-only)
- [ ] Confirm Design studies are stubs or behind Future banners with no runnable deprecated code
- [ ] Confirm `examples/quickstart.py` matches QUICKSTART expected output
- [ ] Confirm Storage today exists and STORAGE_PLUGINS is Future-bannered
- [ ] Run `uv run python scripts/check_docs.py` and `uv run python scripts/build_docs.py`
- [ ] Update this audit’s executive summary if scores change

## Adoption readiness (post-remediation estimate)

| Category | Score |
|---|---:|
| Clarity | 7 |
| Completeness | 7 |
| Discoverability | 6 |
| Learnability | 7 |
| API Documentation | 6 |
| Examples | 7 |
| Contributor Experience | 7 |
| Professionalism | 7 |

Blended ~**6.8 / 10** — honest and newly navigable; still not FastAPI-class reference UX.
