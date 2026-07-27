# Documentation Audit — ETLantic 0.23

> Status: Maintained audit for the 0.23 documentation adoption cut.

## Verdict

Overall quality before this cut: **Fair**. Volume, status vocabulary, and honesty
about bounded production were strong; first-impression clarity, install friction,
API docstring depth, and nav bloat would lose adopters against dbt/Dagster/Prefect.

**Would an evaluator trust the project from docs alone?** Partially. Maintainer
honesty is credible; day-0 funnel and API reference depth were not yet
adopter-grade.

See also [Documentation Audit 0.21](DOCUMENTATION_AUDIT_0_21.md) and
[Documentation Audit 0.20](DOCUMENTATION_AUDIT_0_20.md).

## Scores before remediation (1–10)

| Category | Score |
|---|---|
| Clarity | 4 |
| Completeness | 7 |
| Discoverability | 4 |
| Learnability | 5 |
| API Documentation | 3 |
| Examples | 6 |
| Contributor Experience | 7 |
| Professionalism | 6 |

Weighted feel vs best-in-class: **~5/10**.

## High-priority issues (this cut)

1. Purpose fogged by slogan + category mush (README / docs home)
2. “Stable” language vs PyPI Beta classifier
3. Cold-start `uv add` incorrect on Installation
4. Public API Args/Raises coverage thin (~5% / ~2%)
5. Nav: adopter vs maintainer contamination; duplicate entries
6. Competing “start here”s + unshipped 0.24 on every door
7. Stale version banners (0.18 / 0.21 leftovers) on shipped pages
8. Quickstart identity transform with no mid-flight CLI output
9. Enterprise envelope scattered / oversold in feature tables
10. Broken fence in `TESTING.md`

## Fixed in this cut

1. Audit record (`DOCUMENTATION_AUDIT_0_23.md`) linked from Development hub
2. README + docs home: job-to-be-done first; 0.24 demoted; Beta language
3. Canonical Beta / single-tenant pilot phrasing across day-0 and Evaluate pages
4. Installation: cold-start `uv pip install`; Poetry/Conda; empty-dir `init`;
   contributor checkout separated
5. Quickstart: `python -m etlantic`; expected CLI notes; identity → First Pipeline
6. mkdocs nav dedupe; Contribute section; design studies quarantined under Project
7. Version sweep on Deployment / Production readiness / Security / Engine selection
8. ROADMAP Status for 0.21–0.23 + current-release blurb
9. Curated stable-surface Google-style Args/Returns/Raises + mkdocstrings tighten
10. Docstring coverage gate for surface-inventory symbols (`scripts/check_docs.py`)
11. `TESTING.md` fence fixed; Development README current-first (0.22→0.23)
12. Glossary terms: PipelinePlan, interchange/Gate A, fingerprint, allowlist,
    security_mode, SafeIoPolicy
13. Troubleshooting: top diagnostic codes → remediation
14. Upgrade hub cumulative from-version matrix
15. Evaluate residual lead table; deployment topologies; performance envelope

## Remaining debt

- Broader Args/Raises coverage beyond the curated stable surface
- CLI.md contract test against Typer help
- Docker/devcontainer try path
- From-dbt/Airflow/Dagster migration cookbook
- Search `noindex` for remaining design-proposal stubs if Material supports it
- Commercial support SLO page if a vendor channel appears

## Release gate

Before tagging a docs-impacting release:

- [ ] Root `SUPPORT.md` opening version == package version
- [ ] `SECURITY.md` support table has exactly one current-minor row
- [ ] Beta / single-tenant pilot language agrees on home, FAQ, Capabilities, Evaluator
- [ ] `uv run python scripts/check_docs.py` passes (incl. docstring surface gate)
- [ ] Green path pages agree on `etlantic init` + `python -m etlantic`
- [ ] Design-study examples are not in primary Examples nav
