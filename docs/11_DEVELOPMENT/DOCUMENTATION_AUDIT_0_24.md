# Documentation Audit — ETLantic 0.24

> Status: Maintained audit for the 0.24 documentation adoption cut.

## Verdict

Overall quality before this cut: **Fair**. Coverage of FAQ, troubleshooting,
upgrade, security, and enterprise evaluation was strong; first-run delight,
single green-path narrative, API depth for 0.24 authoring, and version-stamp
hygiene were not yet competitive with dbt / Prefect / Polars.

**Would an evaluator trust the project from docs alone?** Partially — enough
for a bounded pilot; not enough to bet a third-party plugin ecosystem on the
generated API reference and protocol freeze language alone.

See also [Documentation Audit 0.23](DOCUMENTATION_AUDIT_0_23.md) and the
[Archive index](ARCHIVE_INDEX.md).

## Scores before remediation (1–10)

| Category | Score |
|---|---|
| Clarity | 5 |
| Completeness | 7 |
| Discoverability | 4 |
| Learnability | 5 |
| API Documentation | 3 |
| Examples | 5 |
| Contributor Experience | 7 |
| Professionalism | 7 |

Composite feel vs best-in-class: **~5.4/10**.

## High-priority issues (this cut)

1. Dual first-success story (CLI `init` vs checkout `uv run` demos)
2. `init` next-steps printed bare `etlantic` (PATH footgun vs `python -m`)
3. `EXCEPTIONS.md` taught demoted root exception imports
4. Protocol freeze status stuck on “0.22 RC”
5. Capabilities opened with “Residual evaluation lead”
6. 0.24 authoring / service API docs signature-thin; docstring gate too narrow
7. Stale banners (Security through 0.23, Architecture Gate A “0.18”, Plugin SDK
   “Public imports (0.23)”, Development hub migrations, Observability “(0.11)”)
8. `DISTRIBUTION.md` listed unpublished plugin names as peers
9. No PyPI vs clone decision tree
10. Project Archive nav depth + deprecated Sources/Sinks prominence
11. CONTRIBUTING root checklist drifted from docs
12. FAQ thin on programmatic authoring, demoted imports, `security_mode`

## Fixed in this cut

1. `init` next-steps use `python -m etlantic …`
2. Exceptions reference prefers `etlantic.exceptions`
3. Protocol evolution status rewritten for 0.24 / 0.25–0.26 freeze closure
4. DISTRIBUTION published vs hypothetical naming split
5. Version-stamp sweep (Security, Architecture, Plugin SDK, Development hub,
   Observability title)
6. Capabilities leads with “What you can do”; residual limits demoted
7. Single green path across README, docs home, Capabilities, examples README
8. PyPI vs clone callouts on Installation, Quickstart, docs home, examples
9. Root CONTRIBUTING is a thin pointer to the docs checklist (SSOT)
10. FAQ entries for builders/JSON, demoted imports, `security_mode`
11. Quickstart: Windows block, `--with-toml`, `dataframe_engine: local`,
    required aha step, clearer success criteria
12. Google-style Args/Returns/Raises for authoring + service surfaces;
    `check_docs.py` gate expanded
13. Nav: tutorial vs plugin-reference labels; deprecated Sources/Sinks /
    DataContractModel nested; Archive collapsed behind
    [ARCHIVE_INDEX.md](ARCHIVE_INDEX.md)
14. `examples/sample_project/README.md` fleshed out for clone users
15. This audit record linked from the Development hub and Project nav

## Remaining debt

- Docker / devcontainer one-command evaluator sandbox
- From-dbt / Airflow / Dagster migration cookbook
- Full Evaluate diligence dedupe (brief + one deep packet)
- Broader Args/Raises coverage beyond the expanded curated gate
- Public-vs-internal API dump policy (`agents` / `ide` / `notebook`)
- Optional scaffold transform that uppercases `name` (stronger first aha)

## Release gate

Before tagging a docs-impacting release:

- [ ] Root `SUPPORT.md` opening version == package version
- [ ] `SECURITY.md` support table has exactly one current-minor row
- [ ] `scripts/check_docs.py` passes
- [ ] Green path still works: `pip install` → `init` → validate → run
- [ ] Protocol evolution / Plugin SDK banners match the current minor
