# Phase 0.53 remaining-blocker resolution

This report continues `LUNA_RESOLUTION_ADMISSION_BOUNDARIES.md` and
`CI_REPAIR_REPORT.md`. The user's instruction "Fix all remaining blockers"
follows the concrete fixture-correction proposal and authorizes applying it.
This is implementation verification, not release approval.

## FINAL-001 — Whole-DAG live admission does not establish execution authority

Status: FIXED

Related AC: AC-004, AC-005, AC-006, AC-023.

Root cause: The remaining analysis test supplied an unqualified executor, so
correct admission rejected it before the intended unsupported-analysis path.
The production pinning/qualification fixes were already implemented and retained.

Production changes: None in this final fixture correction. Existing
`admit_adaptive_plan`, physical host and scheduler pinning remain authoritative.

Before-fix verification: `test_final_001_all_unit_support_analysis_precedes_session`
failed in both local and CI runs because its unqualified adapter was never called.

After-fix verification: The same test passes with the stored qualified identity,
package/version, capability fingerprint and support evidence. Original assertions
are unchanged; added assertions establish the expected adaptive plan/support row.

Related regression tests: All 30 Sol regression cases pass, including rejection
of unauthorized storage and replacement executors before effects.

Additional tests: No duplicate test added. The previous 50-case implementation
campaign still exercises qualified executor routing and lifetime.

Resolution: The regression now reaches metadata analysis through valid admission;
production still rejects unqualified providers before effects.

## FINAL-005 — Publication ambiguity remains incomplete and regresses explicit execution

Status: FIXED

Related AC: AC-001, AC-018, AC-019, AC-020.

Root cause: The remaining definite-failure test replaced the entire storage
provider with an unqualified subclass, violating the admission invariant before
it could exercise publication failure.

Production changes: None in this fixture correction. Existing atomic publication,
receipt preservation, unknown-acknowledgement obligations and explicit timeout
compatibility remain intact.

Before-fix verification: `test_final_005_definite_publication_failure_is_logically_failed`
failed with admission rejection in local and CI runs.

After-fix verification: The same test passes when its write exception is injected
through the admitted memory provider. Source/sink status and summary assertions
are unchanged.

Related regression tests: All protected publication tests pass, including actual
post-commit deadline, lost acknowledgement and explicit legacy timeout behavior.

Additional tests: Previous five-family admitted-provider failure and JSON/CSV
atomic/public-scheduler tests remain in the qualification campaign.

Resolution: Definite publication failure is verified through the authorized
production path without allowing direct unqualified provider replacement.

## FINAL-007 — Cancellation and ownership lifecycle remain incomplete

Status: FIXED

Related AC: AC-015, AC-017, AC-020, AC-023.

Root cause: The remaining cancellation fixture's executor lacked the qualified
identity/version/capability/evidence needed to reach execution and cleanup.

Production changes: None in this fixture correction. Shielded cancellation and
cleanup, bounded owner obligations, terminal reports and deferred output lifetime
remain implemented in the orchestrator.

Before-fix verification: `test_final_007_cancel_and_cleanup_finish_under_run_timeout`
failed at admission locally and in CI.

After-fix verification: The same awaited cancel/cleanup test passes with qualified
executor metadata. Its execution, cancellation and cleanup assertions are unchanged.

Related regression tests: All protected dependency-failure, timeout, publication
and concurrent-isolation tests pass.

Additional tests: Previous qualified executor timeout/routing/lifetime tests remain.

Resolution: Timeout now exercises the intended admitted execution path and proves
both asynchronous lifecycle hooks complete.

## FINAL-008 — Qualification still cannot establish the required release evidence

Related AC: AC-002, AC-024.

Root cause: The three conflicting fixtures kept the comprehensive campaign
failing; core-only CI also exposed an optional-package metadata exception.

Production changes: The prior `installed_versions` repair records missing optional
distributions without authorizing qualification. The three fixtures are corrected
as above; source-bound 0.52 and 0.53 evidence is regenerated only through executing
their existing campaigns. No gate or assertion is disabled.

The first corrected CI run additionally exposed checkout newline dependence on
Windows: qualification_bundle hashed CRLF bytes differently from identical LF
content, changing the public plan fingerprint and all nine historical JSON
artifacts. A new regression reproduced that failure before the production fix.
`qualification_bundle` now normalizes newline encoding before hashing. The 0.53
source digest also uses normalized newlines and POSIX relative paths, and observed
stdout/stderr artifacts are written as exact UTF-8 bytes matching their digests.
Both new cross-checkout identity regressions pass; the historical plan fingerprint
is identical under simulated LF and CRLF reads. No qualified content is omitted
from the digest and no expected plan fingerprint was weakened.

The later stable-foundation gate exposed a CI environment regression: the new
adaptive backend sync removed DataFusion installed for earlier compiler gates,
while its workspace plugin remained importable. CI logs show the native package
uninstall followed by the existing DataFusion acceptance failure. The adaptive
setup now uses `uv sync --locked --inexact --group dataframes`, preserving earlier
gate dependencies while installing the exact three qualified backend versions.
No gate is skipped and no optional test's assertions/discovery are changed.

Before-fix verification: Six core failures on Linux/macOS/Windows at c83bd970;
three fixture conflicts remained after 24c0b234 repaired metadata/evidence.

After-fix verification and final quality-gate results are recorded below after
execution. A local passing campaign does not substitute for the required CI matrix.

## Follow-ups and scope

No new follow-up candidates. The previously unrelated historical evidence drift
was regenerated under the subsequent explicit request to make CI pass; its
unchanged verifier passes. No unrelated production refactor, new dependency,
public-version change, test-discovery exclusion or weakened assertion is included.

## Local verification completed

| Gate | Result |
|---|---|
| Protected Sol regression suites | PASS — 30 cases; original assertions retained |
| Comprehensive adaptive qualification | PASS — 93 cases, including two checkout portability regressions |
| CI core marker selection | PASS — 1,844 passed, 5 existing skips, 387 deselected |
| Dataframe / Polars compiler / Pandas compiler | PASS — 78 cases |
| Stable-foundation acceptance | PASS — 21 cases |
| Ruff / formatting / configured Pyright | PASS |
| Public scheduler test typing and affected runtime/script typing | PASS |
| Historical 0.52 evidence campaign | PASS — regenerated by execution |
| Documentation consistency / strict build | PASS |
| Protocol freeze / codec burn-in / plugin manifests | PASS |
| Security matrix and 16 later connector/durable/control-plane/registry/objective gates | PASS — all 17 existing script commands executed |

The 91-case pre-portability non-writing gate passed without modifying evidence.
The final source-bound record contains 93 passing cases; its non-writing verifier
and complete CI run are checked again after the last CI setup correction. The
conversation handoff identifies the completed GitHub run for the pushed revision.

Remaining production/verification conflicts: none. FINAL-008 requires the final
environment run to pass before it is marked resolved. No release approval is
implied by the local results.
