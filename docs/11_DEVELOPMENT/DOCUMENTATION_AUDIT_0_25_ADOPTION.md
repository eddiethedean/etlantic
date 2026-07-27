# Documentation adoption audit 0.25 (remediation)

> **Internal project plan / audit record.** Public-adoption review of ETLantic
> 0.25.0 docs and the remediation landed in this pass. Companion to
> [Documentation audit 0.25](DOCUMENTATION_AUDIT_0_25.md).

## Verdict

**Overall: Fair → Good for bounded Beta pilots** after P0/P1 remediation.

Purpose and non-goals remain honest. The green path (Install → Quickstart →
First Pipeline → Engine selection) is now the primary Learn spine. Production
trust examples require `security_mode="production"`, and docs CI fails when
`security_domain="production"` appears without nearby `security_mode`.

Still not a best-in-class enterprise diligence packet or fully deep API
reference for every public symbol.

## Scores (post-remediation)

| Category | Score | Note |
|---|---:|---|
| Clarity | 7 | Green path collapsed; maintainer burn-in language off README day-0 |
| Completeness | 7 | Migration-from-other-tools stub; diagnostics catalog published |
| Discoverability | 7 | Learn slimmed; Support section; Gate A under Transformations |
| Learnability | 7 | Pasteable First Pipeline error; Poetry `--force` documented |
| API Documentation | 5 | Curated docstring gate expanded (`compile_plan`, `explain_plan`); many modules still thin |
| Examples | 6 | Clone tax unchanged (disclosed) |
| Contributor Experience | 8 | CI checklist includes burn-in/manifests; `scripts/README.md` |
| Professionalism | 8 | Trust examples fixed; maturity language aligned to Beta |

**Blended: ~7/10 (Good for Beta pilots).**

## Remediation landed

1. Production Profile/JSON examples set `security_mode="production"`; OPS_PILOT wording fixed; canonical `prod.example.json` linked
2. SECURITY_HOWTO no longer recommends bare `--profile production`
3. `check_docs.py` trust-example gate + bare-production howto ban
4. First Pipeline intentional wiring error is a complete pasteable snippet
5. First-/second-hour CLI normalized to `python -m etlantic`
6. Learn nav slimmed; Support + Earlier releases index; Migration from other tools
7. Docs home collapsed to one green path; README day-0 maintainer block removed
8. Poetry/uv init empty-dir / `--force` recipes
9. Maturity language: OPS_PILOT and COMPATIBILITY use Beta (not Production/stable)
10. Future design stamps (Lifecycle, Architecture resources, Viz banner); PROFILE_PRIMER uses shipped assets
11. FAQ GUI answer toned down; Compare SBOM bullet fixed
12. CONTRIBUTING / RELEASE_PROCESS burn-in + manifest gates; issue template 0.25
13. CHANGELOG Upgrade notes for 0.23–0.25
14. `scripts/README.md`; TESTING.md prefers `test_core.sh`
15. Diagnostics catalog published; curated API docstring gate expanded

## Residual debt

- Broader Args/Raises coverage beyond the curated gate
- Docker / devcontainer evaluator sandbox
- Full from-dbt / Airflow / Dagster cookbooks (stub only today)
- Philosophy essay redirects (Vision / Why / FastAPI / Design Principles)
- SparkForge runnable example under `examples/`
- Dependabot / pre-commit / triage-label polish

## Links

- [Documentation audit 0.25](DOCUMENTATION_AUDIT_0_25.md)
- [Migration from other tools](../01_GETTING_STARTED/MIGRATION_FROM_OTHER_TOOLS.md)
- [prod.example.json](../01_GETTING_STARTED/prod.example.json)
- [Diagnostics catalog](../10_REFERENCE/DIAGNOSTICS_CATALOG.md)
