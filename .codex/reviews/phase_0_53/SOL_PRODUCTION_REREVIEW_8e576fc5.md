# Sol production re-review — phase 0.53

Reviewed production: `8e576fc5d98a216b1a8c526ce826aff095ede2c7`.
Verdict: **NEEDS FIXES**.

## Contract and scope

Authority remains `docs/11_DEVELOPMENT/IMPLEMENTATION_PLAN_0_53.md`, its REQUIRED
BEHAVIOR, AC-001–AC-024, verification matrix and explicit non-scope. Read the
complete latest stored Sol review and current Luna resolution reports; traced
the remediation and its surrounding admission, physical scheduler, member
artifact visibility, boundary operations, executor result, publication and
cleanup/report paths. Inspected the full change boundary against `v0.52.1` and
the current remediation against `01d6a83a`.

This is Experimental, fixture-qualified static local `/2` execution, with Local,
Polars, Pandas and both Arrow directions. Exact supported topology/port and
unfused realization restrictions remain sticky. No SQL/Spark adaptive,
control-plane/durable execution, wider graph qualification, cache-placement
redesign or unrelated repository repair is requested. Python remains >=3.11.
No new substantive scope expansion, dependency/API/wire change or migration was
established in this remediation.

This review changes only two new protected verification cases and this report.
Production, previous assertions, configuration, packaging, documentation and
committed qualification proof are unchanged.

## Acceptance criteria

Evidence includes fresh production inspection, the original 113-case non-writing
campaign, core/optional compatibility gates and independently audited exact-head
CI bundles. Green pre-addition results do not prove the newly exposed invariants.

| AC | Status | Evidence |
|---|---|---|
| AC-001 | VERIFIED | Explicit host-loop compiler case and 1,853-test core compatibility suite pass; `/1` dispatch remains independent. |
| AC-002 | VERIFIED | Five-family, named branch/port/partial topology and public dispatch/support controls pass. |
| AC-003 | VERIFIED | Stored portable/request round trips, marker/envelope tamper and historical wire controls pass. |
| AC-004 | VERIFIED | All-unit analysis, final-dependency and unauthorized/incomplete operation rejection controls pass; admission precedes effects. |
| AC-005 | VERIFIED | Exact live pins/authorization/version/capability/binding/contract/handoff controls pass; no resolver redesign. |
| AC-006 | VERIFIED | Metadata-only analysis, result identity/routing and explicit compiler controls pass; receipt lifecycle regression is separately AC-019. |
| AC-007 | VERIFIED | Effective request, source-only/partial scope, override and stored execution controls pass. |
| AC-008 | VERIFIED | Stored dependency/branch/transitive no-start controls pass; new fences suppress dependent starts after run timeout. |
| AC-009 | VERIFIED | Numeric policy, concurrency precedence/bounds and stored scheduling controls pass. |
| AC-010 | VERIFIED | Real typed empty/nullable five-family portable/sink-preparation differentials pass; unqualified fusion remains closed. |
| AC-011 | VERIFIED | Both real directional Arrow/port routes pass; delayed transfer no longer registers a late route. |
| AC-012 | VERIFIED | Finite collection bounds and execution controls pass; no distributed qualification claim. |
| AC-013 | VERIFIED | Real validation barriers and post-compile schema deadline controls pass. |
| AC-014 | PARTIALLY SATISFIED | Normal checkpoint/reuse/retention controls pass; an expired memory materialization still registers an available checkpoint. FINAL-007. |
| AC-015 | VERIFIED | Complete private member, schema/middleware/durable preparation timeout and no-retry controls pass. |
| AC-016 | VERIFIED | Independent branch, failed dependency and terminal logical outcome controls pass. |
| AC-017 | PARTIALLY SATISFIED | Member/native ownership, transfer/result fences and scheduler cancellation pass; boundary-internal checkpoint registration bypasses the caller fence. FINAL-007. |
| AC-018 | VERIFIED | Normal memory/file overwrite/no-write and admitted provider publication controls pass; only publication commits. Deadline receipt retention is AC-019. |
| AC-019 | REGRESSED | Existing built-in ack-loss/post-commit deadline controls pass; a late admitted executor's known committed receipt is erased by the new fence. FINAL-005. |
| AC-020 | VERIFIED | Existing logical/physical trace/provenance and report migration controls pass; no new count or schema change. |
| AC-021 | VERIFIED | Recursive sensitive-row/native-ref/receipt privacy and namespaced metadata controls pass. |
| AC-022 | VERIFIED | Unsupported consumer/target/durable/dynamic restrictions and explicit compatibility pass. |
| AC-023 | VERIFIED | Concurrent isolation, native buffer/owner retention and repeated executor cleanup controls pass. |
| AC-024 | PARTIALLY SATISFIED | Original 113/113 cases and all nine CI environments pass, with truthful Experimental docs and isolated wheel import; expanded verification exposes two in-scope failures. |

## Previous blockers

| Finding | Status | Verification |
|---|---|---|
| FINAL-001 | VERIFIED FIXED | All-unit analysis, storage denial and post-admission pin replacement controls pass. |
| FINAL-002 | VERIFIED FIXED | Required diamond/fanout/partial/distinct-port support controls pass. |
| FINAL-003 | VERIFIED FIXED | Versioned operations, real handoff/bounds/checkpoint/reuse and four retention controls pass. |
| FINAL-004 | VERIFIED FIXED | Effective/default request, scope, numeric policy and precedence controls pass. |
| FINAL-005 | REGRESSED | Existing writer receipt controls pass; new post-executor deadline fence loses a real returned committed receipt. |
| FINAL-006 | VERIFIED FIXED | Same-runtime concurrent artifact isolation control passes. |
| FINAL-007 | PARTIALLY FIXED | Native/member/schema/durable/transfer deadline controls pass; new boundary checkpoint visibility case fails. |
| FINAL-008 | VERIFIED FIXED | Original non-writing integrity gate and tampered/fabricated/skipped-proof controls pass; nine original CI bundles audited. |
| FINAL-009 | VERIFIED FIXED | Recursive row/native-ref/unknown receipt privacy controls pass. |
| SOL-010 | VERIFIED FIXED | Fresh documentation consistency and strict build pass. |

## Remaining blocker findings

### FINAL-007 — Boundary-internal artifact registration bypasses the run deadline fence

Severity: **High**. Disposition: **BLOCKER**.
Related AC: **AC-017**, related **AC-014**, consequential **AC-024**.

Location: `src/etlantic/runtime/physical_operations.py:176–180` and
`src/etlantic/runtime/orchestrator.py:1936–1950`; other boundary helper branches
also register artifacts internally before returning.

Problem: The caller checks the deadline after `execute_boundary`, but passes the
live run artifact store into that helper. Memory materialization synchronously
copies its value and immediately calls `artifacts.put`. If copying crosses the
effective deadline, the checkpoint is already registered before the caller
delivers cancellation. The caller fence suppresses downstream scheduling but
cannot undo this earlier visibility change.

Evidence: Real qualified Polars Chain, materialization on `first`, 0.5-second run
deadline, and 0.8 seconds of injected latency after the admitted
`ensure_ownership` returns its actual copy. Registration occurred at
5081403.944938333 against deadline 5081403.635684833, and `has(ref.identity)` was
true. The final failed report retained the new `checkpoint:run-...` ref for
`first.result`; second/out were skipped, sink empty, PMEXEC408 present. The
protected test crosses the actual effective deadline inside the same admitted
operation and fails on the available checkpoint assertion, not imports or
admission. Probe: `/tmp/sol053-8e-boundary-probe.log`.

Relationship to current change: This is the existing FINAL-007 late-result
visibility root, outside member-private output staging. The new transfer,
executor result and scheduling fences are genuinely effective; boundary helper
side effects still precede their fence. No unrelated cache redesign is needed.

Why it matters / why this blocks the current change: AC-017 explicitly forbids
late result registration, and the owned checkpoint becomes an available run
artifact after expiry. Failing the run later does not satisfy that invariant.
This is in-scope lifecycle/data-consistency behavior under blocker tests 1, 4
and 6, not optional hardening.

Required behavior: Enforce the deadline/cancellation visibility boundary on
artifacts created by boundary helpers, including their internal registration.
An expired boundary leaves no new available checkpoint or partial output;
preserve previously successful producer outputs, borrowed buffers, safe cleanup
and downstream suppression. Use a coherent boundary-level invariant, not a
special case for this node, plugin or delay.

Acceptance criteria: The protected case passes with the materialization path
entered, PMEXEC408, no new checkpoint ref, no sink effect and no downstream
start. All previous protected/native/retention/receipt controls remain passing;
source-bound qualification is refreshed after unchanged verification passes.

Verification artifact:
`tests/runtime/test_sol_0_53_contract_rereview.py::test_final_007_boundary_deadline_cannot_register_checkpoint`.
Verification status: **FAIL — EXPECTED BLOCKER VERIFICATION**.

**ESCALATION RECOMMENDED:** This stable root has survived repeated fixes at
individual helper/await boundaries. A focused architectural review of all
boundary output commit points or a stronger implementation model is appropriate.
Do not reopen the resolved native ownership or explicit compiler design.

### FINAL-005 — Executor deadline fence erases a known committed publication receipt

Severity: **High**. Disposition: **BLOCKER**.
Related AC: **AC-019**, consequential **AC-024**.

Location: `src/etlantic/runtime/orchestrator.py:1505–1510`, before publication
receipt handling at `1630–1648`.

Problem: The new universal post-executor fence raises on expiry before the host
records the returned publication receipt. The result survives only in the
cleanup record, which is discarded after cleanup; report receipt/reconciliation
metadata remains empty despite an actual committed effect.

Evidence: An exactly qualified public Local physical executor uses the real
memory provider to publish once, crosses the actual run deadline synchronously
before returning a valid `CommitReceipt('committed', publication_id=...)`, and
is cleaned normally. The failed run has sink `[Row(id=1)]`, PMEXEC408, and empty
`etlantic.publication_receipts` and `etlantic.unknown_publications`; no PMADP524
or durable report identifier remains. The test fails specifically on lost
publication evidence. Probe: `/tmp/sol053-8e-publication-probe.log`.

Relationship to current change: Concrete remediation regression. Repeating the
identical exercise with only `01d6a83a`'s orchestrator loaded into the temporary
probe retained the committed receipt in report metadata. The introduced fence
removed it. Stable FINAL-005 covers this already-reviewed receipt/commit outcome
root; no new ID is invented. Baseline: `/tmp/sol053-01d6-publication-probe.log`.

Why it matters / why this blocks the current change: AC-019 requires known
commit evidence to survive later failure and unknown effects to retain
reconciliation IDs. A changed sink plus a plain failed/timed-out report with no
effect evidence makes safe operator reconciliation impossible and can encourage
an unsafe repeat. This is required compatibility and changed publication
correctness under blocker tests 1, 3, 4 and 5.

Required behavior: Preserve validated known committed evidence when fencing a
late executor result. If commit authority/outcome cannot be established, retain
an attributed unknown publication with PMADP524 and safe reconciliation IDs.
Do not turn a late compute result into successful output, repeat committed
publication, advance unproved state or weaken executor identity/privacy checks.

Acceptance criteria: The actual publication occurs once; a non-successful
deadline report retains the receipt's publication ID in its committed receipt
summary or unknown reconciliation entry (with PMADP524 in the latter case).
Existing publication/timeout/ack-loss/privacy controls remain passing. The
verification permits either truthful outcome representation and prescribes no
internal implementation.

Verification artifact:
`tests/runtime/test_sol_0_53_contract_rereview.py::test_final_005_executor_deadline_retains_committed_receipt`.
Verification status: **FAIL — EXPECTED BLOCKER VERIFICATION**.

## Quality gates and verification audit

Local execution is Darwin arm64, Python 3.11.15. Exact-head CI is independently
retrieved evidence, not claimed as local execution of other environments.

| Gate | Executed | Result / classification |
|---|---|---|
| Original non-writing 0.53 campaign | Local, before additions | PASS — 113/113, source_changed=false, committed proof matches source `93e04c4e…191a6`. |
| Configured core suite | Local, discovered before additions | PASS — 1,853 passed, five existing skips, 398 deselected, 48 warnings; 159.47 seconds. |
| Optional dataframe/compiler/conformance | Local | PASS — 62 passed, 194 deselected; 8.08 seconds. |
| Historical non-writing adaptive verifier | Local, before additions | PASS — ten artifacts, 18 criteria; no proof rewritten. |
| Ruff/format/configured Pyright | Local, before/after additions | PASS — 947 Python files formatted, zero Pyright errors/warnings with repository interpreter. Initial bare Pyright selected the wrong interpreter and produced missing-import diagnostics; corrected invocation passes. |
| Documentation consistency / strict build | Local | PASS — consistency 0.52.1 and strict build 23.73 seconds, temporary site output. |
| Surface/diagnostics/protocol/manifests/security/release | Local | PASS — existing static inventories; not a replacement for runtime verification. |
| Wheel / isolated optional-free import | Local | PASS — 0.52.1 wheel and core/physical protocol import without Polars/Pandas/PyArrow. |
| New targeted protected cases | Local | Two EXPECTED BLOCKER VERIFICATION failures, 18 deselected; 11.22 seconds. |
| Expanded qualification | Local, temporary proof | 115 executed, 113 passed, exactly two EXPECTED BLOCKER VERIFICATION failures, zero skips and source_changed=false. All 38 previous protected cases and 12 native cases pass. Committed evidence unchanged. |
| Exact-head CI | Independently retrieved | PASS — all 37 jobs, run 34800127510, head 8e576fc5; predates review additions. |
| Nine exact-head CI proof bundles | Downloaded and independently audited | Each 113/113; all OS/Python pairs, source/scenario/JUnit agreement and stdout/stderr/JUnit SHA-256 pass. Predates review additions. |

The green suite was challenged at two concrete production boundaries that its
existing checks bypass: helper-internal checkpoint registration and receipt
bookkeeping after the newly introduced result fence. Tests preserve real
admitted operations and values; only latency is injected. One case per invariant
is added, with no equivalent permutation expansion or unrelated failing tests.
The original qualification gate passed honestly; missing these cases was a
coverage gap, not proof fabrication. Its current source binding changes because
protected verification changed and must not be rewritten to conceal failures.

Expanded evidence: `/tmp/sol053-8e-review-expanded-proof/qualification.json`,
source `sha256:2a4130e084d0ec79d483ea773ff46567b28d8c0cb90739a0ceee4e125e5c7254`.
The only failures are the two new cases named in the findings above.

## Follow-ups, observations and convergence

New FOLLOW-UPs: **None**. Existing out-of-scope plan issues #83/#86 are unchanged.
Observations requiring action: **None**. No new GitHub issue is needed for these
stable in-scope blockers.

- Previous blocker IDs VERIFIED FIXED: eight.
- Remaining blockers: two — **FINAL-007 and FINAL-005**.
- New root IDs: zero; new blocker attributable to remediation: one (FINAL-005 regression).
- Follow-ups discovered: zero.
- The loop remains bounded; member/native/transfer/scheduling fixes converge,
  but helper visibility and preservation of committed effect evidence remain.

Only FINAL-007 and FINAL-005 enter implementation remediation. Preserve all
verification and required quality gates. Obtain normal Sol PASS before another
independent final release check.

**NEEDS FIXES**
