# Phase 0.53 CI repair

Request: push all changes and make CI pass.

Initial pushed revision: c83bd970. Inspected GitHub Actions run 34788525837
and completed Linux/macOS/Windows core-job logs. All three operating systems
showed the same six failures:

- Historical source-bound adaptive evidence differed from current source.
- Both protected negative evidence tests crashed when optional Polars package
  metadata was absent in the core-only environment.
- Three protected fixture conflicts documented in
  LUNA_RESOLUTION_ADMISSION_BOUNDARIES.md.

## Completed repairs

`check_adaptive_0_53.installed_versions` now records missing optional distributions
as null instead of raising PackageNotFoundError. Missing distributions do not
grant qualification: the existing executed-case, source and digest checks still
reject unqualified evidence. Only the specific missing-distribution exception is
caught. Both unchanged protected negative-evidence tests pass in an isolated
core-wheel environment without optional backend packages (two passed).

Executed `check_adaptive_0_52.py --write`, then its unchanged default verifier.
Both pass. The ten regenerated artifacts retain their existing acceptance
criteria and executed proofs; only source revision and affected plan fingerprints
change. No assertion, expected outcome, gate, or test-discovery exclusion changed.
The existing portable 0.50 verifier also passes.

Ruff check, formatting verification and Pyright for the modified evidence script
pass. Temporary proposal tests initially lacked the repository import path;
rerunning with the correct PYTHONPATH proved the three proposed fixtures pass.

## Required authorization

The user's earlier Fix Release Blockers instructions protect Sol-authored
verification and require adjudication of conflicting artifacts. The requested
fixture-only patch was prepared at
`/tmp/etlantic053-protected-fixture-correction.patch`, reviewed and tested in
temporary copies. It gives both executor fixtures the stored qualified identity,
package/version/capability/evidence, and injects definite write failure through
the admitted memory provider. All existing assertions are preserved; added
assertions require a qualified support row.

That proposal's three focused tests pass. The protected repository test files
remain unchanged pending explicit authorization. No production trust boundary
was relaxed to admit their unqualified providers. A green full CI run cannot be
claimed while these three fixtures still require contradictory admission behavior.

The refreshed 0.53 campaign intentionally records a failed result rather than
fabricating passing qualification. Environment proof and release approval are
not claimed by these repairs. The initial workflow's optional plugin, dataframe,
Spark, SQL, scheduler, FastAPI, IDE and benchmark jobs inspected so far pass;
the core matrix fails on the six findings listed above at the initial revision.
