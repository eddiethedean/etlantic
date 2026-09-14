# Sol production re-review — phase 0.53

Reviewed production: `a0937f484441cdb755abddbc95f9e114d5ef94ea`.
Verdict: **NEEDS FIXES**.

## Contract and scope

Authority remains `docs/11_DEVELOPMENT/IMPLEMENTATION_PLAN_0_53.md`, its REQUIRED
BEHAVIOR, AC-001–AC-024, verification matrix and explicit non-scope. Reconstructed
the contract from the complete plan, latest Sol review, relevant earlier review
and remediation history, current implementation report, production paths,
protected and real-backend verification, documentation, packaging and CI.
Inspected the full touched surface against `v0.52.1` and the latest remediation
against `8e576fc5`.

Scope remains Experimental, fixture-qualified static local `/2` execution on
Local, Polars, Pandas and both Arrow directions. Named topology/port signatures
and qualified unfused realizations remain sticky; unqualified fusion rejects.
No SQL/Spark adaptive execution, durable/control-plane acceptance, wider graph,
producer-skipping cache redesign or unrelated repository cleanup is required.
Core and plugins remain 0.52.1 on this development base; runtime remains >=3.11
with Linux/macOS/Windows qualification on Python 3.11/3.12/3.13. No new dependency,
public wire change, migration or substantive scope expansion was found in the
latest production remediation.

This review changes only one protected verification case and this report.
Production, previous assertions/fixtures, configuration, documentation, package
metadata and committed qualification evidence remain unchanged.

## Acceptance criteria

Fresh proof includes the original non-writing 117-case campaign, all 40 prior
protected Sol cases, 14 native lifecycle cases, 50 real-backend qualification
cases, current core/optional gates, production inspection and independently
audited exact-head CI. The expanded campaign adds one new in-scope invariant.

| AC | Status | Evidence |
|---|---|---|
| AC-001 | VERIFIED | Independent explicit dispatch/host compiler path; fresh 1,855-test core compatibility suite and explicit compiler resource control pass. |
| AC-002 | VERIFIED | Five-family differentials, required named branches, partial chains and distinct directional ports pass; exact support restrictions and public dispatch remain. |
| AC-003 | VERIFIED | Request/stored portable round trips, marker/envelope tamper and historical wire controls pass; admission validates the actual executable envelope. |
| AC-004 | VERIFIED | All-unit support analysis, final-dependency/storage denial and incomplete boundary controls pass; admission precedes runtime session/effects. |
| AC-005 | VERIFIED | Exact live compiler/dataframe/executor/storage pins and authorization/version/capability/binding/contract/handoff checks inspected; replacement/denial controls pass. |
| AC-006 | PARTIALLY SATISFIED | Metadata analysis, exact result identity/output routing and explicit compatibility pass. A valid terminal failed executor result loses its logical outcome. SOL-011. |
| AC-007 | VERIFIED | Effective/default request, source-only/partial scope, overrides and stored execution controls pass; no runtime re-slicing or native substitution. |
| AC-008 | VERIFIED | Stored dependency/branch/transitive no-start controls pass; new probe also suppresses failed-branch publication while independent work completes. |
| AC-009 | VERIFIED | Numeric validation, Profile/request concurrency precedence and bounded stored scheduling controls pass. |
| AC-010 | VERIFIED | Real typed empty/nullable five-family portable and sink-preparation differentials pass; current rows reject unqualified fused realizations. |
| AC-011 | VERIFIED | Both real Arrow directions, distinct port routing, conversion location and delayed-transfer fencing pass. |
| AC-012 | VERIFIED | Actual finite collection/bounds success/failure cases pass; distributed execution is not qualified. |
| AC-013 | VERIFIED | Real contract validation barriers, affected publication suppression and post-compile schema deadline controls pass. |
| AC-014 | VERIFIED | Named checkpoint/reuse/retention cases pass. Private boundary commit and file rollback preserve prior bytes, later replacement and borrowed producer values. |
| AC-015 | VERIFIED | Qualified member-private schema/middleware/durable preparation timeouts and no-retry/unsafe-policy controls pass; no wider fusion claim. |
| AC-016 | PARTIALLY SATISFIED | Built-in independent/transitive failure controls pass. A failed qualified executor branch remains pending when a later independent branch succeeds. SOL-011. |
| AC-017 | VERIFIED | Native drain/abandon/owner retention, complete member fence, transfer, scheduler and boundary-internal deadline cases pass; private output commit inspected. |
| AC-018 | VERIFIED | Only publication commits; actual memory/JSON/CSV overwrite, no-write, receipt and destination-lock controls pass. |
| AC-019 | VERIFIED | Known executor commit evidence is recorded after identity validation and before cancellation delivery. Late committed receipt, ack-loss, unknown, post-commit and explicit writer controls pass. |
| AC-020 | PARTIALLY SATISFIED | Normal physical/logical provenance and metadata controls pass; new probe has a failed physical unit but a pending logical step and zero failed summary count. SOL-011. |
| AC-021 | VERIFIED | Recursive row/native-ref/receipt privacy and namespaced metadata controls pass; safe receipt projection invokes no provider serializer. |
| AC-022 | VERIFIED | Closed unsupported target/consumer/durable/dynamic restrictions and explicit compatibility pass; no changed qualification claim. |
| AC-023 | VERIFIED | Concurrent run isolation, buffer lifetime, repeated executor cleanup and safe owner obligations pass; the fresh failed-branch probe cleans every started executor. |
| AC-024 | PARTIALLY SATISFIED | Original 117/117 passes locally and in nine audited CI environments; wheel/docs/gates pass. Expanded required verification has one expected SOL-011 failure. |

## Previous blockers

Stable FINAL identifiers are preserved; they are not renamed to SOL identifiers.

| Finding | Status | Verification |
|---|---|---|
| FINAL-001 | VERIFIED FIXED | Whole-DAG/all-unit analysis, denied/replaced storage and post-admission executor replacement controls pass; pins inspected. |
| FINAL-002 | VERIFIED FIXED | Exact required diamond/fanout/partial-chain and both-direction distinct-port cases pass. |
| FINAL-003 | VERIFIED FIXED | Versioned actual collection/validation/checkpoint/reuse and all four retention controls pass. |
| FINAL-004 | VERIFIED FIXED | Effective/default request, stored portable execution, source-only scope, numeric policy and Profile precedence controls pass. |
| FINAL-005 | VERIFIED FIXED | New late executor committed-receipt regression and existing ack-loss/post-commit/explicit writer/file receipt controls pass. Identity-validated safe evidence precedes the deadline fence; unknown obligations survive missing acknowledgement. |
| FINAL-006 | VERIFIED FIXED | Same-runtime concurrent artifact isolation remains passing. |
| FINAL-007 | VERIFIED FIXED | Boundary-internal checkpoint deadline regression and all member/native/schema/durable/transfer/cleanup controls pass. Boundary and executor output sets commit privately; staged-file rollback controls pass. |
| FINAL-008 | VERIFIED FIXED | Fresh original non-writing gate and tampered/fabricated/skipped-proof controls pass; nine source/output-bound CI bundles independently audited. Expanded gate correctly exposes the new failure. |
| FINAL-009 | VERIFIED FIXED | Recursive row/native-ref/unknown receipt privacy controls remain passing. |
| SOL-010 | VERIFIED FIXED | Fresh documentation consistency and strict build pass; Experimental claims remain truthful. |

## New blocker

### SOL-011 — Failed executor branch disappears from the final logical report

Severity: **Medium**.
Disposition: **BLOCKER**.
Related AC: **AC-016**, related **AC-006/AC-020**, consequential **AC-024**.

Location:

- `src/etlantic/runtime/orchestrator.py:1582`: non-successful results raise before
  their logical outcomes are projected.
- `_execute_physical_units`, `guarded`, at `2117`: generic compute executor
  failures are recorded physically without terminalizing their logical members.
- `2110`, `2159` and `2175`: the remembered error is batch-local and propagated
  only if that failing batch drains the entire pending set. Later independent
  successful batches discard it.
- `_execute_physical`/`_build_report`, `1297` and `2193`: pending contributes to
  run-level failure selection but remains pending in the step report and is
  omitted from the failed summary count.

Problem: A qualified executor may return an identity-valid terminal failed
result with an attributed failed logical outcome. The host rejects the result
before copying that outcome. If independent work remains, the scheduler skips
dependents correctly but forgets the error before final report construction.
The failed member remains pending with zero attempts and no diagnostic, while
its physical trace is failed. This is incomplete failure projection/retention,
not a dependency-readiness or publication-isolation defect.

Evidence: Exact supported Local Fanout, captured concurrency two, admitted
`etlantic.physical.local/1` executor with matching package/version/capability/
evidence. Left compute returns `PhysicalUnitResult(status="failed")` with
`PhysicalLogicalOutcome("left", "failed", attempts=1, failure_stage="transform",
code="PMADP520")`. Right completes and uses the real memory provider to publish
once. All six started executor invocations are cleaned.

Observed final report:

```text
run: partial
raw: succeeded/1; shared: succeeded/1
left: pending/0; left_out: skipped/0
right: succeeded/1; right_out: succeeded/1
summary: total=6, succeeded=4, failed=0, skipped=1, cancelled=0
diagnostics: []
left sink effects: 0; right sink effects: 1
```

The regression confirms independent publication and cleanup before failing on
`pending != failed`. It enters the actual admitted executor/scheduler/report
path; no production failure projection or ready queue is mocked. Probe:
`/tmp/sol053-a093-failed-executor-probe.py`; targeted result:
`/tmp/sol053-a093-targeted.log`.

Relationship to current change: This public physical executor/scheduler path
was introduced by phase 0.53 and lies inside its required failure/reporting
boundary. Inspection of `8e576fc5` confirms the early result rejection and
batch-local error already existed; this is a previously uncovered phase defect,
not a regression caused by the latest artifact/receipt fixes. It has a different
root from the resolved deadline visibility and publication evidence findings.

Why it matters: Operators and report consumers cannot establish the failed
logical member's terminal outcome or executed attempt; physical and logical
reports disagree and terminal summary counts do not account for every selected
node. A partial run label alone does not preserve this required evidence.

Why this blocks the current change: AC-016 explicitly requires one terminal
report per selected logical node, and AC-020 requires physical/logical report
agreement. The changed supported public executor path demonstrably violates
both. Blocker tests 1, 4 and 6 apply. Independent successful branch completion
is allowed, so remediation must preserve it rather than fail or suppress every
branch. This is not a demand for unrelated repository perfection.

Required behavior: Validate and retain attributed terminal executor failure
outcomes and safe execution evidence without exposing failed outputs. A later
independent successful batch must not erase earlier failures. Final logical
reports are terminal with truthful attempt/count/diagnostic evidence; dependent
skips, independent publication, cleanup, receipt retention and identity/privacy
checks remain intact. Fix this at the shared failure projection/retention
boundary, not by recognizing the fixture's names or special-casing Fanout.

Acceptance criteria:

1. The valid failed left result produces a terminal failed left report with the
   returned one executed attempt and an attributed safe PMADP520 diagnostic.
2. The report is partial with six logical reports, four succeeded, one failed
   and one skipped; physical failure and logical failure agree.
3. Left sink is skipped with zero effects; independent right sink succeeds with
   exactly one effect; every started executor is cleaned.
4. Existing protected cases, latest receipt/artifact fixes and required gates
   remain passing. Refresh source-bound evidence only after verification passes.

Verification artifact:
`tests/runtime/test_sol_0_53_contract_rereview.py::test_sol_011_failed_executor_branch_has_terminal_logical_report`.

Verification status: **FAIL — EXPECTED BLOCKER VERIFICATION**. Targeted run:
one failed, two passed, 18 deselected, 9.51 seconds. The two latest previous
blocker cases pass in that same run. Expanded campaign: 118 executed, 117 passed,
only SOL-011 failed, zero skips, source_changed=false.

## Quality gates and verification audit

Local execution is Darwin arm64, Python 3.11.15. Other environments below are
independently retrieved CI evidence, not claimed as local execution.

| Gate | Executed | Result / classification |
|---|---|---|
| Original non-writing 0.53 campaign | Local, before addition | PASS — 117/117, source_changed=false; source `bf1e6411…44d30` agrees with committed proof. |
| Configured core marker suite | Local, before addition | PASS — 1,855 passed, five existing skips, 400 deselected, 48 warnings; 156.89 seconds. |
| Optional dataframe/compiler/conformance | Local | PASS — 62 passed, 194 deselected; 12.21 seconds. |
| Historical non-writing adaptive verifier | Local, before addition | PASS — ten artifacts, 18 criteria; no proof rewritten. |
| Ruff/format/configured Pyright | Local, before/after addition | PASS — 947 files formatted, zero type errors/warnings using repository interpreter. |
| Documentation consistency / strict build | Local | PASS — consistency 0.52.1 and strict build 26.35 seconds to temporary site. |
| Surface/diagnostics/protocol/manifests/security/release | Local | PASS — existing gates; static security inventory is not substituted for runtime proof. |
| Wheel / isolated optional-free import | Local | PASS — built 0.52.1 wheel and core/physical protocol imports without Polars/Pandas/PyArrow. |
| Latest two previous blockers + new targeted case | Local | Two PASS; one EXPECTED BLOCKER VERIFICATION failure, specifically missing terminal logical failure. |
| Expanded qualification | Local, temporary proof | 118 executed, 117 PASS, exactly one EXPECTED BLOCKER VERIFICATION failure; zero skips, source_changed=false. |
| Exact-head CI | Independently retrieved | PASS — all 37 jobs, run 34803470014, head a0937f48; predates this review addition. |
| Nine exact-head CI proof bundles | Downloaded and independently audited | Each 117/117; source/scenario/JUnit agreement and stdout/stderr/JUnit SHA-256 verified on all OS/Python pairs; predates addition. |

The green suite was challenged at the public terminal-failure/independent-branch
integration boundary. Existing qualified executor fixtures establish successful
routing and cancellation; built-in failure fixtures use a different state
projection path. Their passing results did not constrain returned failed
executor outcomes followed by later independent success. The original gate and
CI proof were honest; this is a coverage gap, not fabricated evidence. One
behavioral verification case is added for this root, with no weakened tests,
gate bypasses, equivalent permutation expansion or unrelated failing artifacts.

Expanded evidence: `/tmp/sol053-a093-expanded-proof/qualification.json`,
source `sha256:f54a3d25e25f7309c89558153f5633ea8eca625a3342e50028163c6b1e8c3a85`.
Committed qualification proof remains unchanged; it cannot certify the newly
expanded verification until the root defect is fixed and proof refreshed.

## Follow-ups, observations and convergence

New FOLLOW-UPs: **None**. Existing out-of-scope plan tracking #83/#86 remains.
Observations requiring action: **None**. No new GitHub issue is required for the
in-scope blocker.

- Latest previous blockers resolved: **two**, FINAL-007 and FINAL-005.
- Historical blocker IDs verified fixed: **ten**.
- Blockers remaining: **one**, SOL-011.
- New blockers attributable to latest remediation: **zero**.
- Newly discovered in-scope phase root: **one**.
- New follow-ups discovered: **zero**.
- Convergence: the loop shrinks from two blockers to one; neither resolved root
  is reopened. The remaining work is bounded to executor failure reporting and
  retention, not a new architecture or repository-wide implementation iteration.

Only **SOL-011** enters Luna/Terra remediation. Preserve all verification,
required gates and the resolved artifact/receipt behavior. Obtain normal Sol
PASS before another independent final release check.

**NEEDS FIXES**
