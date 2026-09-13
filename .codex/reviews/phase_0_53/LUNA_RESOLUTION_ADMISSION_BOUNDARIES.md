# Phase 0.53 bounded blocker remediation

Authoritative contract: `docs/11_DEVELOPMENT/IMPLEMENTATION_PLAN_0_53.md`.
Authoritative findings: `SOL_PRODUCTION_REREVIEW_7150f226.md` in this directory.
Starting implementation: `dc8889c6`. Stable FINAL identifiers are retained;
FINAL-006 was already resolved and is not reopened. This report is implementation
self-verification, not independent approval.

The starting focused campaign had 35 passing cases. That narrow result did not
establish the missing admission, boundary, ownership or qualification invariants
identified by Sol. This remediation adds 50 implementation-side cases and runs
both protected review suites unchanged. The resulting combined campaign executes
91 cases: 88 pass and three fail because their unqualified fixtures conflict with
the approved admission sequence. The recorded qualification result is **fail**;
it must not be used as release approval.

## Resolution report

### FINAL-001 — Whole-DAG live admission does not establish execution authority

Status: **VERIFICATION CONFLICT**

Related AC: AC-004, AC-005, AC-006, AC-023.

Root cause: Admission previously accepted insufficient live identity/evidence,
and later execution could rediscover mutable providers instead of using the
admitted adapters. Direct storage-map mutation and live portable replacements
could bypass the stored contract.

Production changes: `adaptive_admission.admit_adaptive_plan` resolves and pins
selected executor, storage, dataframe, compiler and contract dependencies; checks
inventory distribution versions, authorization, identities, protocol versions,
capabilities and evidence; and restricts compiler discovery to selected targets.
`physical_host.stored_implementations` uses stored portable descriptors.
`scheduler.LocalScheduler` and `orchestrator.LocalOrchestrator` pass/use those pins.
Source/sink binding descriptors and resolved contract fingerprints are captured.

Before-fix verification: Sol reported replacement-after-admission FAIL at
7150f226. The starting 35-case campaign passed, but did not prove complete live
dependency qualification.

After-fix verification: Protected live-storage, append-mode and executor
replacement controls pass. The protected all-unit-analysis control fails because
its `PhysicalExecutorInfo("rejecting", "test-provider", "1")` is rejected before
calling that unqualified adapter's analysis.

Related regression tests: Both protected review suites, adaptive execution and
planner tests; five-family stored differential and qualified-executor tests.

Additional tests: Qualified executor routing/lifetime proves execution with live
admitted adapters and resolved inputs; retry-safety rejection proves zero reads.

Resolution: Production enforces the approved trust boundary. Sol must adjudicate
the fixture conflict below before this finding can be reported FIXED.

### FINAL-002 — Required topology support remains graph-derived and incomplete

Status: **FIXED**

Related AC: AC-002, AC-024.

Root cause: Submitted graphs generated their own support evidence; exact diamond,
partial chain and directional assignment matching were incomplete.

Production changes: `adaptive_support.qualification_bundle` loads independently
packaged, digest-bound rows/observations from `adaptive_support.json`.
`support_row_for` matches exact role/port wiring and contiguous assignment cuts,
including the five-edge diamond and source/step partial chains. Rows require exact
qualified backend/plugin versions and supported operation/policy modes. These
rows qualify unfused units; fused realizations require separate evidence and
are rejected rather than inheriting singleton qualification.

Before-fix verification: Sol's exact diamond failed at 7150f226; the starting
focused campaign passed after preliminary topology remediation, without the
independent packaged operation/version proof now required.

After-fix verification: Protected fanout, diamond and source-only tests pass;
all 50 implementation-side qualification cases pass.

Related regression tests: Adaptive planner tests and both Sol review suites.

Additional tests: Real single-target diamond/fanout execution on local, Polars
and Pandas; distinct two-port transfer in both directions; partial step scope;
five-family empty/nullable stored execution against explicit baselines.

Resolution: Required shapes match packaged evidence independently of the
submitted plan's graph hash. Full release/environment qualification remains
tracked separately under FINAL-008.

### FINAL-003 — Physical boundary operations and result routing remain incomplete

Status: **FIXED**

Related AC: AC-006, AC-008, AC-010, AC-011, AC-012, AC-013, AC-014, AC-020.

Root cause: Boundaries could authorize truthy flags or report success without an
operation; collection could discard a converted destination value; custom
executor inputs, logical outcomes and output routes were incomplete.

Production changes: `physical_operations.validate_operation/execute_boundary`
defines closed versioned descriptors and executes finite collection, contract
validation, owned materialization and checked reuse. Named checkpoints use safe,
atomic writes with digest/security/producer/contract/expiry checks. Planning emits
same-target collection units too. Orchestrator preserves transferred frames,
passes routed inputs/adapters, validates complete custom results before registering
outputs, and attributes failed validation boundaries to their logical owner.

Before-fix verification: Sol's bare checkpoint flag authorized no-op execution
and effects at 7150f226; starting focused controls were green but did not exercise
the complete actual operation paths.

After-fix verification: Protected bare-flag rejection and transfer-location
controls pass. New actual collection/checkpoint/validation/routing tests pass.

Related regression tests: Both review suites; dataframe and compiler tests.

Additional tests: Collection max_rows boundary pass/fail across five families;
actual validation invocation and failed publication barrier across three engines;
workspace materialization/reuse across three engines; directional dual ports;
custom executor routed inputs/outcomes and publication-delayed sink completion.

Resolution: Boundary success reflects an executed declared operation. Unsupported
descriptors/policies reject admission; converted destination ownership is retained.

### FINAL-004 — Effective inputs and public /2 scheduler typing remain incomplete

Status: **FIXED**

Related AC: AC-003, AC-006, AC-007, AC-009.

Root cause: Effective input capture/precedence and stored portable rehydration were
incomplete, and public scheduler types did not accurately include adaptive plans.

Production changes: Planning captures effective selected bindings/contracts and
operation descriptors; physical host restores stored portable implementations
without a live pipeline class. Scheduler uses `PlanDocument` with concrete adaptive
type narrowing and retains schema-marker rejection. Compiler selection uses
Profile's public snapshot rehydration rather than its incompatible dataclass init.

Before-fix verification: Sol reported source-only, Profile precedence and public
typing failures at 7150f226. Preliminary fixes made the starting focused cases
pass; strengthened pins exposed a Profile reconstruction regression during this
remediation, reproduced and corrected before handoff.

After-fix verification: Protected selection, source-only, default request,
Profile concurrency, numeric policy and stored portable controls pass. Configured,
protected-public-test and affected-module Pyright checks pass without ignores.

Related regression tests: Adaptive planner/execution and protected review suites.

Additional tests: Five-family serialized plan execution; step-ending selection;
public scheduler JSON/CSV file publication tests caught the reconstruction defect
and both pass after the production fix.

Resolution: Executable descriptors use captured effective input; public typing
accepts legitimate /2 plans while retaining the explicit /1 route.

### FINAL-005 — Publication ambiguity remains incomplete and regresses explicit execution

Status: **VERIFICATION CONFLICT**

Related AC: AC-001, AC-018, AC-019, AC-020.

Root cause: Writes/acknowledgements were discarded or mapped without preserving
uncertainty, and adaptive timeout mapping affected legacy explicit writes.

Production changes: `adaptive_publication.publish_file` performs destination-locked
atomic JSON/CSV overwrite and returns a typed receipt. Orchestrator publishes only
at the publication unit, retains committed receipts before sink completion, records
unknown PMADP524 obligations on commit timeout/cancellation, and preserves explicit
write timeout behavior. Unknown IDs are stable bounded reconciliation identities.

Before-fix verification: Sol's actual post-commit deadline and explicit-timeout
controls failed at 7150f226; the starting focused campaign passed those preliminary
fixes but lacked qualified file publication and preserved real receipt coverage.

After-fix verification: Protected lost-ack, post-commit-deadline and explicit
timeout controls pass. The original definite-failure control now rejects its direct
unqualified `runtime.storage["memory"] = FailingStorage()` replacement at admission.

Related regression tests: Protected publication controls; backend/codec tests.

Additional tests: Definite write failure through the admitted memory provider in
all five families; concurrent atomic JSON/CSV overwrite; actual public scheduler
file output/receipt; custom executor sink remains pending until committed publication.

Resolution: Authorized publication behavior is demonstrated. Sol must adjudicate
the unqualified-provider fixture conflict before this finding can be FIXED.

### FINAL-007 — Cancellation and ownership lifecycle remain incomplete

Status: **VERIFICATION CONFLICT**

Related AC: AC-015, AC-017, AC-020, AC-023.

Root cause: Awaited cancellation/cleanup ran in cancelled scopes, outputs could be
reclaimed before consumers/publication, primary errors could obscure obligations,
and retry safety was not established before effects.

Production changes: Admission validates effective retry safety for selected members.
Orchestrator shields cancellation/drain/cleanup, applies configured abandonment
bounds, retains PMADP523 obligations and primary errors, builds terminal cancellation
reports, and defers executor cleanup through output-consumer/publication lifetime.
Validated outputs are registered only after a complete successful result.

Before-fix verification: Sol's awaited cancel/cleanup timeout control failed at
7150f226. It passed in the starting focused campaign while accepting an unqualified
executor, which did not prove the combined admission/lifecycle contract.

After-fix verification: Protected transitive propagation, partial behavior and
concurrent isolation controls pass. The protected cancellation control rejects
`PhysicalExecutorInfo("cancel-sentinel", "sol-sentinel", "1")` before execution.
The matching qualified executor completes both awaited lifecycle hooks under timeout.

Related regression tests: Both protected suites and adaptive execution tests.

Additional tests: Qualified timeout executor proves awaited cancel/cleanup drain;
qualified source/step/sink executor proves shared routed output lifetime survives
until publication; unsafe retry rejects before source reads.

Resolution: Admitted lifecycle behavior is demonstrated; the conflicting fixture
requires Sol adjudication. This does not claim fake-adapter tests independently
qualify every native cancellation behavior or fused realization.

### FINAL-008 — Qualification still cannot establish the required release evidence

Status: **PARTIALLY FIXED**

Related AC: AC-002, AC-024.

Root cause: The former verifier could accept skipped/fabricated narrow proof and
ignored digests/executed identities/environment coverage.

Production changes: `scripts/check_adaptive_0_53.py` executes five test modules,
parses actual JUnit, rejects skipped/missing/duplicate/failed required cases, binds
source before/after execution, sanitizes observations and verifies committed file
digests, case identities/counts and environment. CI records separate Linux/macOS/
Windows × Python 3.11/3.12/3.13 artifacts with exact backend versions. Packaged
support contains 50 actually passing physical-case observations and 13 closed rows.

Before-fix verification: Sol's fabricated/skipped record was accepted at 7150f226;
the starting focused control passed after preliminary validation fixes, without
the complete real-backend/environment campaign.

After-fix verification: Both protected tampered/fabricated/skipped rejection tests
pass. The real 91-case campaign correctly records FAIL with 88 passes/three conflicts,
and therefore cannot establish the required fully passing release evidence.

Related regression tests: All five campaign modules; core wheel isolated import.

Additional tests: The 50 real physical qualification cases described above.
The earlier 48-case physical campaign also passed on macOS Python 3.12 and 3.13;
the latest two file-integration cases were executed on Python 3.11. Linux/Windows
matrix jobs have not been demonstrated locally and are not claimed passing.

Resolution: False-positive evidence is rejected and meaningful proof is recorded.
What remains: Sol must resolve the three protected verification conflicts, then
the complete campaign/non-writing gate and required CI environments must actually
pass. A failed record deliberately remains a failed gate; it is not regenerated
into fabricated qualification.

### FINAL-009 — Recursive protocol privacy remains bypassable by receipts

Status: **FIXED**

Related AC: AC-021.

Root cause: Arbitrary receipt serialization and unbounded nested metadata could
forward source rows/native values through ostensibly safe protocol summaries.

Production changes: `physical_protocol` uses closed, bounded recursive projections,
typed known receipt/ref summaries, safe counters/statuses, redacted arbitrary text,
and opaque/hashed unknown identities/tokens. It never calls arbitrary receipt
`to_dict` or serializes native payloads. Physical failures expose bounded attributed
diagnostics instead of provider exception payloads; metric writers remain namespaced.

Before-fix verification: Sol's unknown receipt exposed synthetic rows at 7150f226;
starting focused privacy controls passed, without the stronger closed recursive
projection and writer audit now implemented.

After-fix verification: All four protected row/native-ref projections and the
unknown-receipt payload test pass. Diagnostic/protocol stability gates pass.

Related regression tests: Both protected suites; protocol/diagnostic/core tests.

Additional tests: Qualification output/receipt assertions exercise normal report
paths. No equivalent privacy permutations were added merely to increase test count.

Resolution: Unknown provider serialization cannot bypass the safe report boundary.

### SOL-010 — New evidence documentation still fails a required docs gate

Status: **FIXED**

Related AC: AC-024.

Root cause: The evidence page lacked required maturity/status metadata and did
not accurately explain executable qualification versus a release decision.

Production changes: Evidence README declares Experimental and documents exact
dependencies, observed failure records, sanitized proof, supported-environment
claims and conditional unfused qualification. API_PLAN_RUNTIME documents boundary
descriptors, pins, publication receipts and deferred lifecycle cleanup.

Before-fix verification: Sol's unchanged docs consistency gate failed at 7150f226;
starting focused runtime tests did not cover this documentation contract.

After-fix verification: Unchanged `scripts/check_docs.py` and strict
`scripts/build_docs.py --strict` both pass.

Related regression tests: Documentation consistency includes examples/anchors;
public surface/agent guidance gates also pass.

Additional tests: None needed for the status declaration; actual behavior is
covered by the implementation-side integration tests.

Resolution: Required documentation gates pass and describe implemented behavior
without claiming independent approval.

## Protected verification conflicts requiring Sol adjudication

All protected test files and Sol reports are unchanged. No assertion was weakened,
test skipped, gate disabled, or behavior special-cased to a reproducer.

1. **FINAL-001** — `test_final_001_all_unit_support_analysis_precedes_session`:
   the fixture supplies an unqualified executor but requires calling its analysis.
   The approved Whole-DAG Live Admission sequence checks authorization/evidence and
   exact provider qualification in steps 3–4 **before** support analysis in step 5;
   AC-005 prohibits using denied adapters. Required behavior is reject without
   invoking the unqualified adapter. The analysis-before-session invariant can be
   verified using a matching qualified executor that returns unsupported. Invoking
   the current fixture would bypass the ordered qualification contract.
2. **FINAL-005** — `test_final_005_definite_publication_failure_is_logically_failed`:
   the fixture directly replaces the memory provider with an unqualified subclass,
   yet expects reads and publication. FINAL-001 explicitly identifies direct map
   mutation as a bypass and requires exact qualification before effects; AC-004/005
   require admission rejection. The approved behavior is reject that replacement.
   Definite publication failure must instead be injected through an admitted
   qualified provider; the new five-family tests demonstrate that behavior. Allowing
   this replacement would restore the direct-map bypass Sol required removing.
3. **FINAL-007** — `test_final_007_cancel_and_cleanup_finish_under_run_timeout`:
   the fixture's executor identity/package/version/capability/evidence do not match
   the stored qualification, but it requires execution. AC-005/006 and FINAL-001
   require rejection before that execution. The lifecycle invariant requires a
   matching qualified executor; the new awaited-hook timeout test demonstrates it.
   Executing the existing fixture would break admission to satisfy cancellation.

Sol must adjudicate these verification contracts; Luna has not changed them or
silently reinterpreted their expectations. FINAL-008's release proof remains open
as a consequence. The requested handoff is adjudication, not approval.

## Follow-up report

Existing Sol follow-ups/observations: Historical 0.52 source-bound evidence drift
remains unchanged. Sol independently established it at the parent reviewed commit;
the historical evidence regeneration test still fails. No historical artifacts
were rewritten to make the gate green. FINAL-006 remains previously resolved.

New follow-up candidates: None. No unrelated cleanup or dependency/public-version
changes were incorporated. Exact optional versions were installed in test
environments without altering package dependency ranges or lock metadata.

## Quality gate report

| Gate | Executed | Result | Notes |
|---|---|---|---|
| 50-case physical qualification, macOS Python 3.11 | Yes | PASS | Real local/Polars/Pandas and directional transfer paths; all 50 cases pass inside the combined campaign. |
| Combined five-module campaign | Yes | FAIL — OPEN BLOCKER | 88 passed / 3 verification conflicts / 91 executed; committed record says fail, source_changed=false. |
| Default non-writing 0.53 verifier | Yes | FAIL — OPEN BLOCKER | Exit 1 rejects the failing committed proof; SHA-256 of all evidence files unchanged before/after. Both protected false-proof rejection controls pass. |
| CI core marker command, unchanged selection | Yes | FAIL — OPEN BLOCKER | Fresh run: 1,838 passed, 5 skipped, 387 deselected, 4 failed; three conflicts plus the historical evidence failure below. No test exclusions added. |
| Historical test_final_052_006_evidence_regenerates_cleanly | Yes | FAIL — PRE-EXISTING/UNRELATED | Sol independently recorded parent-commit source-bound drift; no historical artifact remediation included. |
| tests/dataframe, tests/polars_compiler, tests/pandas_compiler | Yes | PASS | 78 passed on the final implementation. |
| Earlier 48-case physical campaign, macOS Python 3.12 | Yes | PASS | 48 passed; isolated environment with exact optional versions. Does not claim the latest two additional integration cases ran on 3.12. |
| Earlier 48-case physical campaign, macOS Python 3.13 | Yes | PASS | 48 passed; same limitation for the latest two integration cases. |
| Ruff check / formatting verification | Yes | PASS | All checks passed; 945 files formatted. |
| Configured Pyright | Yes | PASS | Zero errors/warnings. |
| Pyright protected public scheduler test file | Yes | PASS | tests/runtime/test_sol_0_53_rereview.py; zero errors/warnings. |
| Additional Pyright affected runtime modules | Yes | PASS | Admission, publication, physical operations/host/protocol, orchestrator and scheduler; zero errors/warnings. |
| Documentation consistency | Yes | PASS | Unchanged check_docs.py including example/anchor/surface checks. |
| Strict docs build | Yes | PASS | Unchanged build_docs.py --strict; output outside repository. |
| Pipeline codec burn-in | Yes | PASS | 32 fixtures across eight versions. |
| Protocol freeze | Yes | PASS | Six core /1 families remain stable. |
| Public surface inventory | Yes | PASS | 19 curated exports and 17 lazy namespaces. |
| Diagnostic stability | Yes | PASS | 36 shipped families. |
| Agent guidance | Yes | PASS | Drift check passes. |
| Security matrix | Yes | PASS | 21 controls, 16 mandatory / 5 partial; existing verification-path inventory gate, not a claim of new comprehensive security testing. |
| Plugin manifests | Yes | PASS | 15 packages. |
| Existing release metadata gate | Yes | PASS | For repository version 0.52.1; not approval for phase 0.53. |
| Core, Polars and Pandas wheel/sdist builds | Yes | PASS | Final builds written outside repository. |
| Isolated core wheel import | Yes | PASS | No Polars/Pandas/PyArrow imported; 13 support rows and 50 observations packaged. |
| Linux/Windows supported-environment qualification jobs | No | NOT RUN — ENVIRONMENTAL/UNAVAILABLE | Workflow configured; local macOS evidence is insufficient to claim those jobs passed. |
| Latest full 91-case campaign on Python 3.12/3.13 | No | NOT RUN — OPEN VERIFICATION CONFLICT | Earlier physical runs documented above; deferred pending adjudication, not an unavailable Python runtime or a passing campaign claim. |
| Additional typo-path typing invocation | Attempted | NOT RUN — ENVIRONMENTAL/UNAVAILABLE | tests/runtime/physical_typing_0_53.py does not exist; superseded by the actual protected public-test typing command above, which passed. |
| Additional guessed backend directories | Attempted | NOT RUN — ENVIRONMENTAL/UNAVAILABLE | tests/polars and tests/pandas were not test directories; superseded by the actual 78-case backend/ compiler command above. |
| Final diff / protected-artifact audit | Yes | PASS | git diff --check passes; both protected Sol test files and Sol-authored reports unchanged. |

The configured Linux/Windows CI environments are unavailable on this local macOS
host. Additional 3.12/3.13 execution is possible, but cannot produce the required
passing full release campaign until Sol resolves the protected contract conflicts;
these full runs are deferred rather than misreported as passing.

No quality gate, marker selection, fixture infrastructure, protected assertion,
dependency range, migration, or public release version was weakened. Qualification
JUnit/process files are deliberately sanitized, source-bound evidence artifacts;
temporary builds, logs, environments and debug output are not committed.

## Remediation summary

Blockers received: 9

Blockers fixed: 5

Blockers remaining: 4

Verification conflicts: 3

Escalations: 0

New follow-up candidates: 0

**SOL ADJUDICATION REQUIRED**
