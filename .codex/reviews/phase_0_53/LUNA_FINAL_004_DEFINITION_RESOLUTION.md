# FINAL-004 — Portable definition execution remediation

Baseline: `3f565858ef996d28629a360ed76c56f79cd4a3f6`.
Authority: the independent final release check of that candidate and
`docs/11_DEVELOPMENT/IMPLEMENTATION_PLAN_0_53.md`. Remediation scope contains
only FINAL-004. This is an implementation report, not independent release approval.

## FINAL-004 — Portable definition planning remains incomplete

Status: **FIXED**

Related AC: **AC-002, AC-003**; existing AC-001/AC-007 compatibility and
effective-request controls remain passing.

Root cause: Adaptive candidate analysis read portable definitions only through
a live transformation class method. `TransformationDefinition` instead stores
immutable portable IR as data. Executable descriptor generation independently
repeated the live-class assumption. Definition graphs also omit Python contract
type objects, so the planner captured no contract schema fingerprints for
admission after serialization. Finally, definition planning did not supply the
default RunRequest already used by class planning.

Production changes:

- `src/etlantic/planning/adaptive.py`: `_portable_definition` reconstructs the
  portable definition from stored IR using the existing DTCS fingerprint and
  requirement extractor. `_implementation_records` uses the same resolver for
  candidate and execution-record generation. `_contract_fingerprints` resolves
  contract identities through the same resolver used by stored-plan admission.
  Admission still checks the captured schema digest and rejects unavailable or
  changed contracts.
- `src/etlantic/plan/planner.py`: `_build_plan_from_definition` supplies the
  default RunRequest for adaptive definitions, matching class planning.

Before-fix verification: The final-review probe in
`/tmp/sol053-final-probes.py` was rerun against the unchanged baseline. The
request-supplied parameter class path executed successfully, but the equivalent
definition failed with `PMADP320` (no viable target for `step`). The final-review
Chain probe had also demonstrated the same failure in both planning APIs.

After-fix verification: The same parameter probe passed all four class/definition
and plain/report planning variants, including verified stored-plan execution
and expected output `[2, 3]`. The new implementation regression suite exercises
the original Chain reproducer through both planning APIs and executes its stored
plan successfully.

Related regression tests: The unchanged protected effective-request, explicit
override, independent fallback, serialized fallback collision, scheduler,
adaptive wire and report-namespace tests passed. Both existing protected Sol
physical suites also passed in the 128-case qualification campaign.

Additional tests: `tests/runtime/test_definition_portable_0_53.py` adds 19 cases:

- Direct and JSON-round-tripped definitions with default requests, both public
  planning APIs, stored-plan round trips and execution. A guard makes live
  transformation-method fallback fail if attempted.
- Request-provided required parameters across definition and plan serialization.
- Public `arun_pipeline` execution of a serialized definition.
- Class/definition placement, contract fingerprint, output and logical-status
  parity across Local, Polars, Pandas and both Arrow transfer directions.
- Missing and invalid portable IR reject in both planning APIs.

Resolution: Supported definitions now carry their portable data through
analysis, descriptor capture and stored execution. Both authoring forms use
the same default request and captured contract authority. Existing explicit,
fallback, eligibility and admission behavior remains covered by unchanged
regression tests. No remaining part of the received blocker is known to fail.

## Follow-Up Report

Existing Sol FOLLOW-UPs: GitHub #145 (historical Medallantic fingerprints) and
#146 (deadline-test startup timing) remain separate and were not remediated.

New Follow-Up Candidates: None. The local benchmark timing failure was also
reproduced on unchanged v0.52.1 in the same container, matching the prior
independent review's environmental result.

## Quality Gate Report

Fresh execution used an isolated Linux aarch64 Python 3.11.16 environment with
Polars 1.42.1, Pandas 2.3.3 and PyArrow 25.0.0. The source repository was mounted
read-only for that environment; approved edits and generated evidence were
copied explicitly between the workspace and isolated checkout.

| Gate | Executed | Result | Notes |
|---|---|---|---|
| New and protected/adjacent targeted tests | Yes | PASS | 91 passed, including all 19 new cases |
| Configured core suite | Yes | PASS | 1,767 passed; 24 optional skips; 404 deselected |
| Adaptive 0.53 evidence generation | Yes | PASS | 128/128; source unchanged during execution |
| Adaptive 0.53 default non-writing verification | Yes | PASS | Fresh 128/128; committed proof matches source |
| Historical adaptive 0.52 generation and verification | Yes | PASS | 10 artifacts; 18 criteria |
| Ruff lint and formatting | Yes | PASS | Whole repository plus changed files |
| Pyright | Yes | PASS | Configured project and explicit changed-source/test check |
| Release/manifests | Yes | PASS | All packages remain 0.53.0 |
| Documentation checks and build | Yes | PASS | No contract/documentation relaxation |
| Surface/diagnostic/protocol/security/guidance | Yes | PASS | Existing gates unchanged |
| Stable foundation | Yes | PASS | All 21 acceptance tests |
| Compiler drift and portable 0.50 | Yes | PASS | Existing compatibility evidence |
| Pipeline/sibling/isolated codec burn-ins | Yes | PASS | Existing gates |
| Connector/durable/CP4/registry/CP-GA/objective gates | Yes | PASS | Fake-mode gates retain their existing fake-mode scope |
| Medallantic/SparkForge | Yes | PASS | 73 passed |
| Build/package smoke | Yes | PASS | 24 wheels and sdists; clean core import without optional backends |
| Microbenchmark | Yes | FAIL — PRE-EXISTING/UNRELATED | Same thresholds fail on unchanged v0.52.1 in this container |
| Final diff / source fingerprints | Yes | PASS | Protected tests unchanged; no gates weakened |

The benchmark observed plan/validate times of 0.057378s/0.027977s against
0.028750s/0.017250s ceilings. Unchanged v0.52.1 observed 0.053267s/0.027167s
in the same environment. No benchmark baseline or tolerance was changed.

Generated historical artifacts differ only in repository revision. The 0.53
record differs only in source revision and observation time; scenario results,
sanitized JUnit and aggregate output hashes are unchanged. Current source hash:
`sha256:edae4350f8c26f4899a8028836633348613a70719e25e7d747392eebb4f93920`.
Existing Sol verification artifacts, CI, package versions and dependency ranges
were not altered. Post-push CI results are reported separately in the handoff.

## Remediation Summary

- Blockers received: 1
- Blockers fixed: 1
- Blockers remaining: 0
- Verification conflicts: 0
- Escalations: 0
- New follow-up candidates: 0

**READY FOR SOL RE-REVIEW**
