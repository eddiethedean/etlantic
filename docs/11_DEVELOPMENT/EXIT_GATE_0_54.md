# 0.54 local implementation exit gate

> **Status: 0.54.0 release published; adaptive graduation remains pending.**

This gate records local adaptive implementation verification, not independent
approval or production readiness. All fourteen candidate rows remain
Experimental; publication does not promote any row to Available.

Required local checks cover public conformance, bounded source/fusion execution,
exact row/direction differentials, failure/ownership/publication, compatibility,
deterministic planning/resource limits, evidence integrity, decision safeguards,
documentation and packaging. The frozen
`evidence/adaptive_0_54/case_catalogue.json` maps all 24 local and all 24 programme
criteria to exact full pytest identities and all fourteen row signatures.

Run `python scripts/check_adaptive_0_54.py` for temporary local observations or
`--write --output NEW_DIRECTORY` to retain a fresh run, including failures.
`--verify-index PATH` is read-only and never executes evidence commands.
`--aggregate DIRECTORY` builds an integrity index and then verifies completeness;
it never creates a go decision. Missing cells, failed/skipped/xfail/xpass cases,
wrong pins, escaping paths, duplicate cases/cells, hashes or source mismatches
return nonzero.

Actual Linux/macOS/Windows × Python 3.11/3.12/3.13 observations are required only
for a cross-platform qualification claim, not this handoff. CI is wired to upload
failed observations and aggregate after all matrix jobs. No remote observation,
reviewer, release owner or go decision is fabricated locally.

The [implementation report](IMPLEMENTATION_REPORT_0_54.md) records actual checks,
remaining findings and applicable limitations. Next: **Sol — Production Code Review**.
