# Luna resolution — FINAL-007 complete member deadline

Authoritative remediation set:
[SOL_PRODUCTION_REREVIEW_a0d13478.md](SOL_PRODUCTION_REREVIEW_a0d13478.md).
Only FINAL-007 is assigned. The prior native ownership and explicit compiler
compatibility fixes remain intact. The protected Sol test and review carried
into this turn are preserved unchanged.

## FINAL-007 — Post-compile schema work can bypass the member deadline and publish late output

Status: **FIXED**.

Related AC: **AC-015, AC-017**; consequential **AC-024**. Compatibility with
AC-001/023 remains verified by the existing protected cases.

Root cause: Artifact registration occurred inside the member body, before
schema inspection and middleware had necessarily completed. The helper-local
deadline check could not enforce the complete member's deadline. Synchronous
work after that check could prevent delivery of the timeout callback, then
expose outputs and report success.

Production changes:

- `runtime/artifacts.py`, `AttemptArtifactStore`: adaptive attempt writes are
  private and reads fall through to the run store without copying/reclaiming
  borrowed inputs. Complete output sets become visible only after the member
  and middleware finish and the effective deadline/cancellation check passes.
  Durable preparation is also checked before visibility. Failure restores
  previous artifact files/removes new files; cleanup failure is retained for
  an owner obligation while preserving the primary exception.
- `runtime/artifacts.py`, `check_attempt_deadline`: delivers pending
  cancellation and checks the effective clock deadline around the cooperative
  checkpoint, including expiry during synchronous work.
- `runtime/orchestrator.py`, `_execute_node`: uses a fresh private store per
  adaptive member attempt. The timeout scope includes the complete middleware
  body and artifact preparation/commit. Unsuccessful attempts discard pending
  sink preparation and private outputs; unresolved durable cleanup records
  PMADP523 with actual unit/member/attempt identifiers. Explicit calls continue
  using their existing store and compiler execution path.
- `runtime/dataframe_exec.py`: removes the superseded helper-local deadline
  fence; native worker ownership is unchanged. No schema/input special case is
  added.
- `docs/06_EXECUTION/EXECUTION_MODEL.md`: documents the member completion,
  deadline, output visibility and durable rollback behavior.

Before-fix verification: The protected
`test_final_007_post_compile_schema_deadline_fences_registration` was rerun
before production edits and failed as reported: `succeeded` rather than
`timed_out`; one failure, 17 deselected. The actual admitted schema path ran.

After-fix verification: The same unmodified protected test passes. All 38
protected Sol cases pass in the full campaign, together with native member/run/
external cancellation, host-resource explicit compiler, no-timeout-retry,
cooperative cleanup, publication and isolation cases. The final non-writing
campaign executes/passes 112 cases, with no required skip or source drift.

Related regression tests: Both complete Sol files and the physical five-family
qualification suite run in the campaign. Focused lifecycle verification passes
15 cases. Explicit dataframe/compiler/conformance selection passes 62 cases.
The configured core suite passes 1,853 cases with five existing skips.

Additional tests in `tests/runtime/test_native_execution.py` (six new cases):

- Parameterized source/transform/sink middleware completion past the member
  deadline: outputs remain private while middleware unwinds, the member times
  out once, and no sink effect occurs (three cases).
- External cancellation after the body returns: no private transform output
  becomes available and the public cancelled report is retained.
- Deadline during real durable preparation: old file bytes are restored, a
  new file is removed and neither output is exposed in the parent store.
- Successful multi-port durable completion: both ports/files appear together
  in the run store and borrowed input identity/ownership survives stage cleanup.

A separate temporary runtime probe with an outer run deadline and synchronous
post-body middleware also passed: failed run, no late transform artifact and
zero sink effect. It adds no repository verification artifact.

Resolution: Deadline enforcement now belongs to the complete adaptive attempt's
output visibility boundary. Source, transformation and sink preparation use the
same mechanism. Schema work, conversion, middleware unwinding and durable
preparation cannot expose successful late output. The existing timeout
classification/no-retry and downstream suppression logic receives the failure
naturally. The change resolves the repeated boundary-placement problem without
redesigning native execution, explicit execution or the physical scheduler.

## Requirements self-check

| Requirement | Status | Evidence |
|---|---|---|
| Complete member deadline before output visibility/success | IMPLEMENTED | Protected schema test; three late middleware cases |
| No timeout retry / no downstream publication | IMPLEMENTED | Protected native deadline; new one-attempt/zero-effect assertions |
| Cancellation after body completion | IMPLEMENTED | New public cancellation case and outer run-deadline probe |
| Durable preparation failure leaves no available partial outputs | IMPLEMENTED | Real file rollback and complete multi-port success cases |
| Native owner/buffer lifecycle and explicit compatibility preserved | IMPLEMENTED | All earlier protected FINAL-007 cases and existing native implementation cases |
| Required campaign/evidence | IMPLEMENTED locally | 112/112 executed/pass; non-writing proof check matches source |
| Documentation / packaging / dependencies / migrations | IMPLEMENTED / unchanged contract | Docs gates and isolated wheel import pass; no new dependency, version or schema change |

## Follow-up report

Existing Sol FOLLOW-UPs: none newly assigned; existing plan tracking #83/#86 is
not implemented. The optional protected-file typing observation is unchanged.

New follow-up candidates: **None**. Private output staging and durable rollback
are directly required by the same deadline/visibility invariant, not separate
feature work.

No known unresolved implementation issue, verification conflict or architecture
escalation remains within FINAL-007. Abandoned native workers may still finish
later according to the existing bounded ownership contract; their result is
fenced and their buffers retained. Crash recovery and global transactions remain
outside scope.

## Quality gates

| Gate | Executed | Result | Notes |
|---|---|---|---|
| Before-fix protected schema deadline | Yes | FAIL — OPEN BLOCKER | Reproduced before edits |
| Targeted protected/native checks after initial fix | Yes | PASS | 9 passed, 14 deselected |
| Complete focused lifecycle selection | Yes | PASS | 15 passed, 14 deselected |
| Final phase 0.53 write campaign | Yes | PASS | 112 executed/pass, zero required skips, source_changed=false |
| Final non-writing phase 0.53 verifier | Yes | PASS | 112/112; committed source/output proof matches |
| Historical adaptive evidence refresh | Yes | PASS | Unchanged verifier, 10 artifacts / 18 criteria; source fingerprint refresh only |
| Configured core suite | Yes | PASS | 1,853 passed, 5 existing skips, 397 deselected, 48 warnings; historical regeneration check included |
| Polars/Pandas dataframe, compiler and public conformance selection | Yes | PASS | 62 passed, 194 deselected |
| Ruff / format | Yes | PASS | 947 Python files formatted |
| Configured Pyright | Yes | PASS | Zero errors/warnings |
| Extra typing: artifact store and implementation tests | Yes | PASS | Zero errors/warnings |
| Documentation consistency | Yes | PASS | Existing external-URL report only |
| Strict documentation build | Yes | PASS | 23.37 seconds; temporary site output |
| Core wheel build and isolated import | Yes | PASS | Core/physical protocol/attempt store import without Polars/Pandas/PyArrow |
| Outer run deadline after completed body | Yes | PASS | Temporary runtime probe, no repository edits |
| Final diff/whitespace inspection | Yes | PASS | Production changes map only to FINAL-007; protected assertions/gates unchanged |

Final source fingerprint:
`sha256:bb5198725caeb1a4da88244527a9b01302862cb45d5e04de8aa03ea44c7c2bbb`.
Exact pushed-revision CI results will be supplied in the conversation handoff;
the prior revision's green CI is not reused as proof of this remediation.

Blockers received: 1
Blockers fixed: 1
Blockers remaining: 0
Verification conflicts: 0
Escalations: 0
New follow-up candidates: 0

**READY FOR SOL RE-REVIEW**
