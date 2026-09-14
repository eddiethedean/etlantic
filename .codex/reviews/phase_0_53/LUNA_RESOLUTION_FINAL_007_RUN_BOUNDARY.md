# Luna resolution — FINAL-007 physical run-deadline boundary

Authoritative remediation set: the latest Sol final release check. Only
FINAL-007 was assigned. FOLLOW-UPs and observations remain out of scope.

## SOL-XXX — FINAL-007 run-deadline fencing remains bypassable outside member execution

Status: **FIXED**

Related AC: **AC-017**, consequential **AC-024**.

Root cause: The prior remediation fenced adaptive member output publication,
but physical transfer, boundary, and protocol-executor paths could register
results after a synchronous operation crossed the run deadline. The scheduler
also computed another ready batch without first delivering cancellation or
checking the effective deadline.

Production changes: `src/etlantic/runtime/orchestrator.py` now applies the
shared `check_attempt_deadline()` fence before announcing/starting every
physical unit, after protocol executor completion and validation before routing
handles, after synchronous transfer conversion before recording a route, after
boundary operations before storing output, and before each scheduling batch.
The existing member-private `AttemptArtifactStore`, native ownership, explicit
compiler loop, publication receipts and cleanup paths are unchanged.

Before-fix verification: A real Polars→Pandas chain with a 0.15-second run
deadline and 0.3 seconds of synchronous interchange latency returned from
conversion after the effective deadline, registered `second.source`, and
started `second`. A delayed admitted protocol executor likewise exposed late
outputs. These probes were recorded in `/tmp/sol053-final-transfer-deadline-probe.log`
and `/tmp/sol053-final-executor-deadline-probe.log`.

After-fix verification: The same real delayed-transfer exercise now records no
route, skips `second`, leaves the sink empty, and reports `PMEXEC408`. The new
implementation regression `test_run_deadline_fences_synchronous_physical_transfer`
passes, as do the protected Sol cases and all existing native lifecycle tests.

Related regression tests: The focused lifecycle selection passes 16 tests. The
complete phase 0.53 campaign passes after including the new transfer case. Core,
dataframe/compiler/conformance, static, documentation, packaging, and CI gates
remain passing.

Additional tests: `tests/runtime/test_native_execution.py` adds the real
Polars→Pandas delayed-handoff case. It establishes that a synchronous physical
transfer cannot register a route or start its dependent after the run deadline;
it is distinct from the existing member-body and native-worker tests.

Resolution: Physical execution now treats the run deadline as a visibility and
scheduling invariant across all physical-unit paths. A delayed operation must
fail before its result becomes an input or artifact, and no new unit starts once
the scope is expired or cancelled. The existing timeout report and downstream
suppression behavior then apply without retrying the expired work.

## Requirements self-check

| Requirement | Status | Evidence |
|---|---|---|
| Physical result/route cannot become visible after run deadline | IMPLEMENTED | Delayed real transfer test and post-executor fence |
| Scheduler stops starting units after cancellation/deadline | IMPLEMENTED | Pre-unit and pre-batch fences; delayed transfer regression |
| Native/member ownership and explicit compiler compatibility remain intact | IMPLEMENTED | Protected Sol/native suites and core compatibility gates |
| Qualification and docs remain source-bound and truthful | IMPLEMENTED | 0.53 verifier and docs gates |

## Follow-up report

Existing Sol FOLLOW-UPs: none assigned to this remediation.

New follow-up candidates: none.

Final source-bound qualification fingerprint: `sha256:93e04c4effdf2464ab4cf5b4e84fa4afcf5fb9e9223e3a13e6ad54071fd191a6`.
The campaign executes 113/113 cases, including 38 protected Sol cases and 12
native/lifecycle cases.

## Quality gate report

| Gate | Executed | Result |
|---|---|---|
| Focused protected/native tests | Yes | PASS — 16 passed |
| Phase 0.53 write and non-writing evidence | Yes | PASS — 113/113 source-bound cases |
| Core and dataframe/compiler/conformance suites | Yes | PASS |
| Ruff, formatting and Pyright | Yes | PASS |
| Historical adaptive verifier | Yes | PASS |
| Documentation consistency and strict build | Yes | PASS |
| Wheel build and isolated import | Yes | PASS |
| CI exact-head run for predecessor | Yes | PASS — 37/37 jobs on `01d6a83a`; the final remediation commit is pushed and its run is reported in the handoff |

Blockers received: 1
Blockers fixed: 1
Blockers remaining: 0
Verification conflicts: 0
Escalations: 0
New follow-up candidates: 0

**READY FOR SOL RE-REVIEW**
