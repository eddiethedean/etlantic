> Status: Maintained audit for ETLantic 0.18.0 documentation adoption cut
> (updated after published-0.18 public-adoption remediation).

# Critical Documentation Audit — ETLantic 0.18

This audit records the documentation condition after the 0.18 adoption
remediation **and** the published-0.18 hygiene pass. It succeeds
[DOCUMENTATION_AUDIT_0_17.md](DOCUMENTATION_AUDIT_0_17.md) as the maintained
release artifact. Reassess when release posture or public package behavior
changes.

## Executive Summary

- **Overall documentation quality: Good.**
- **Would I personally trust this project based on the documentation?** Yes,
  for evaluation and documented single-tenant reference deployments, after
  reading Capabilities, Evaluator, and Production readiness—and after the
  pip-vs-clone / Gate A API gaps closed in this pass.
- **Why?** Critical factual errors from earlier cuts remain fixed; green path
  is encoded in Learn nav; PyPI users get paste-ready Quickstart and embedded
  profile JSON instead of dead-end `examples/` paths; Plugin SDK is labeled
  shipped; Gate A `etlantic.interchange.tabular` is in the API reference;
  status/pins on adopter pages target 0.18.0.

Earlier self-rating of “Good” before the first remediation was **too
generous** against FastAPI/Pydantic/dbt onboarding craft. Honesty was already
strong; this pass closed remaining adoption hygiene.

## Remediated in prior cut

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

## Remediated in published-0.18 pass

1. Pip vs clone callouts; Quickstart is the pip path; `examples/` requires checkout
2. Embedded production profile JSON in Capabilities CI starter; fixed
   `profiles/prod.example.json` link misdirection
3. Docs home: Plugin SDK labeled shipped; hero CTA Quickstart | Installation;
   minimal example includes `plan()` and pins `==0.18.0`
4. Learn nav reordered to green path; Guides nested; Design Proposals “do not start here”
5. Canonical stability sentence in SUPPORT / SECURITY / FAQ / README
6. One install story (packages primary, extras equivalent); `python -m pip`
7. Gate A `::: etlantic.interchange.tabular` + Compatibility row + Plugin SDK
   interchange capability + conformance smoke
8. Architecture + Troubleshooting Gate A sections
9. Wave17 docs aligned to Polars-only companion
10. Status/pin sweep (RUNTIME, ENV_VARS, CI, RUN_REPORTS, SECURITY, What’s New historical)
11. CORE_CONCEPTS Extract/Step/Load headings; FAQ / PROJECT_STRUCTURE hygiene

## Remaining debt (not blocking 0.18 docs gate)

- Refresh quantitative performance baselines on current 0.18.x
- Further demote Design Proposals (search-only / collapsed theme)
- Versioned docs site per release
- Thin companion pages for SQL extras / dataframe_parity (README links only today)
- Broader typed Returns on public Pipeline methods (`Any` cleanup is code)

## Release documentation gate checklist

Before tagging a minor/patch docs cut:

- [ ] Grep adopter pages for impossible pins (`<0.18` style empty ranges)
- [ ] Grep for teaching `Source`/`Sink` as current (exclude migration/deprecated pages)
- [ ] Confirm green path step 4 is Engine selection (not Capabilities-only)
- [ ] Confirm Design studies are stubs or behind Future banners with no runnable deprecated code
- [ ] Confirm `examples/quickstart.py` matches QUICKSTART expected output
- [ ] Confirm Storage today exists and STORAGE_PLUGINS is Future-bannered
- [ ] Confirm pip users are not directed to wheel-missing `examples/` without a clone note
- [ ] Run `uv run python scripts/check_docs.py` and `uv run python scripts/build_docs.py`
- [ ] Update this audit’s executive summary if scores change

## Adoption readiness (post published-0.18 remediation)

| Category | Score |
|---|---:|
| Clarity | 8 |
| Completeness | 8 |
| Discoverability | 7 |
| Learnability | 8 |
| API Documentation | 7 |
| Examples | 8 |
| Contributor Experience | 7 |
| Professionalism | 8 |

Blended ~**7.6 / 10** — honest, navigable, and pip-safe for first success;
still short of FastAPI-class reference UX on design-proposal demotion and
performance baselines.
