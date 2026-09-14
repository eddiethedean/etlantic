# Luna resolution — boundary visibility and publication evidence

Authoritative remediation set:
`SOL_PRODUCTION_REREVIEW_8e576fc5.md`. Only FINAL-007 and FINAL-005 are in scope.
All protected Sol verification is preserved unchanged.

## FINAL-007 — Boundary-internal artifact registration bypasses the run deadline fence

Status: **FIXED**.
Related AC: **AC-017**, related **AC-014**, consequential **AC-024**.

Root cause: The boundary helper received the live run artifact store. Its own
checkpoint/rejected-output registration preceded the caller's deadline check;
named files were written before the complete boundary could commit visibility.

Production changes:

- `runtime/orchestrator.py`, physical boundary path: give every boundary an
  `AttemptArtifactStore`, prepare its entire output set privately, then commit
  before exposing a collection route or releasing dependencies. Record owner
  cleanup obligations if rollback fails.
- Physical executor output sets use the same private commit so durable output
  preparation cannot bypass this shared physical-result visibility invariant.
- `runtime/artifacts.py`, `AttemptArtifactStore.stage_text/commit`: stage named
  checkpoint text with artifact refs; drain owned file I/O, enforce the effective
  deadline after preparation, and publish the whole lookup set without yielding.
  Failure restores previous bytes (including CRLF) or removes newly created files.
  Destination locking protects preimage capture; rollback preserves a later
  writer's replacement. Borrowed parent inputs are never copied or cleared.
- `runtime/physical_operations.py`, `execute_boundary`: queue named checkpoint
  persistence through the private store instead of writing eagerly. Serialized
  checkpoint format remains unchanged.

Before-fix verification:
`test_final_007_boundary_deadline_cannot_register_checkpoint` failed on an
available checkpoint after the actual effective deadline. The real Polars probe
retained that checkpoint in its failed run report.

After-fix verification: The unchanged protected case passes. The same real probe
retains the previously successful producer refs but no checkpoint ref in the run
store, skips the dependent, writes no sink output and reports PMEXEC408.

Related regression tests: Complete protected/native/qualified-boundary selection
passes 102 tests; the final focused lifecycle/receipt/checkpoint selection passes
20 tests, including admitted executor output routing.

Additional tests: `test_staged_checkpoint_deadline_restores_files` has two
implementation-side cases: exact prior bytes/new-file rollback, and preservation
of a subsequent writer's replacement. Both preserve borrowed producer handles
and leave no available pending checkpoint.

Resolution: Boundary-internal outputs and owned files now participate in the
complete physical operation's visibility commit. Expired preparation cannot
replace the successful producer or register its new checkpoint in the run.

## FINAL-005 — Executor deadline fence erases a known committed publication receipt

Status: **FIXED**.
Related AC: **AC-019**, consequential **AC-024**.

Root cause: Deadline delivery preceded publication receipt bookkeeping. A
returned known commit survived only in transient cleanup state and disappeared
from the failed run's report.

Production changes: The admitted executor path creates a run/unit-specific
unknown obligation before starting publication. After result identity
validation, it uses the existing safe receipt projection to retain committed or
rolled-back evidence before any deadline checkpoint. Missing/untrusted/unknown
acknowledgements retain safe reconciliation IDs and PMADP524. Known evidence
does not authorize late output visibility, sink success or state advancement.
Normal publication avoids duplicate receipt summaries; no blind executor retry
is added and existing identity/privacy checks remain.

Before-fix verification:
`test_final_005_executor_deadline_retains_committed_receipt` failed because the
sink changed once but both receipt and unknown-publication summaries were empty.

After-fix verification: The unchanged protected case passes with one committed
effect, non-successful deadline report and retained committed publication ID.
Additional real executor probes verify lost acknowledgement and returned unknown
outcome retain reconciliation identifiers and PMADP524 without repeating the
effect.

Related regression tests: Existing built-in ack-loss, post-commit deadline,
explicit writer timeout, qualified executor publication/cleanup and recursive
receipt privacy verification pass in the complete campaign.

Additional tests: No equivalent duplicate of Sol's committed receipt regression
was added; implementation probes exercise distinct lost/unknown acknowledgement
paths.

Resolution: Execution cancellation cannot erase already established publication
evidence. A failed run truthfully retains either known commit evidence or the
unknown effect requiring reconciliation.

## Requirements self-check

| Requirement | Status | Proof |
|---|---|---|
| FINAL-007 / AC-014, AC-017: no late boundary checkpoint availability | IMPLEMENTED | Unchanged protected boundary test; real qualified probe |
| Owned named file preparation rolls back without reclaiming borrowed inputs | IMPLEMENTED | Two staged-file implementation regressions |
| FINAL-005 / AC-019: retain committed evidence across deadline failure | IMPLEMENTED | Unchanged protected publication test |
| Missing/unknown acknowledgement retains reconciliation identity | IMPLEMENTED | Real admitted executor probes; existing receipt controls |
| Identity/privacy and explicit/native compatibility | IMPLEMENTED | Protected, native, core and compatibility suites |
| AC-024 source-bound evidence and truthful documentation | IMPLEMENTED | Final write/non-writing campaign and documentation gates |

## Follow-up report

Existing Sol FOLLOW-UPs: none assigned; plan tracking #83/#86 remains outside
this remediation. New follow-up candidates: none. No unrelated observation or
quality-gate relaxation was implemented.

## Quality gates

| Gate | Executed | Result |
|---|---|---|
| Protected and related lifecycle/qualification tests | Yes | PASS — 102 passed; final focused selection 20 passed |
| New staged checkpoint rollback tests | Yes | PASS — two cases |
| Final 0.53 write and non-writing qualification | Yes | PASS — 117/117; source_changed=false |
| Final core marker suite | Yes | PASS — 1,855 passed, five existing skips, 400 deselected |
| Dataframe/compiler/conformance | Yes | PASS — 62 passed, 194 deselected |
| Ruff, formatting, configured Pyright | Yes | PASS — 947 formatted files, zero type errors |
| Historical adaptive evidence verifier | Yes | PASS — ten artifacts, 18 criteria |
| Documentation consistency and strict build | Yes | PASS |
| Static surface/diagnostics/protocol/manifests/security/release | Yes | PASS |
| Wheel build and isolated optional-free import | Yes | PASS |

Final 0.53 source fingerprint:
`sha256:22610e9acd02c7c7038038187df0dec2a87cebee4238a3678d066ff121b650b9`.
Qualification proof is refreshed only through the existing unchanged verifier.
The exact pushed-commit CI result is reported in the conversation handoff.
No dependency, package version, migration, CI gate or public serialization change
is required. There are no known unresolved implementation issues within scope.

Blockers received: 2
Blockers fixed: 2
Blockers remaining: 0
Verification conflicts: 0
Escalations: 0
New follow-up candidates: 0

**READY FOR SOL RE-REVIEW**
