# Findings Ledger 0.41 — Durable Submission and State (CP3)

> **Status: Gate-ready** — ETLantic **0.41.0** CP3 exit. Open **P0 count is 0**.
> **CP3 ≠ production multi-tenant** (**0.43**).

## Severity policy

From [IMPLEMENTATION_PLAN_0_41](IMPLEMENTATION_PLAN_0_41.md):

| Severity | Meaning | Release treatment |
|---|---|---|
| **P0** | Lost accepted work, duplicate unsafe effects, stale fencing publish, cross-tenant durable disclosure, secret/row leakage in durable records, production multi-tenant false claim | Must close before 0.41 |
| **P1** | Material recovery, migration, chaos evidence, or adoption risk | Close or defer with owner, mitigation, target phase, and non-blocking rationale |
| **P2** | Localized usability, performance, or maintainability defect | May defer with owner and target |
| **P3** | Cosmetic or opportunistic improvement | Backlog |

Changing severity without written rationale does not close a finding.

## Locked dispositions

Recorded in
[ADR-018: Durable Submission and State](adr/ADR-018-DURABLE-SUBMISSION-AND-STATE.md).
Do not reopen without a written finding and migration plan.

| Decision | Outcome | Notes |
|---|---|---|
| Accept ≠ execute | Submission + outbox in one transaction | No embedded broker |
| CP1 vs CP3 | SubmissionStore + optional DurableWorkStore | Dual-write allowed; host ops on `/v1/durable/*` |
| Idempotency | Tenant/workspace/operation/issuer-qualified principal | Input mismatch → conflict |
| Admission | Per-tenant in-flight limit | Full quotas → **0.42** |
| Leases | TTL + fencing + heartbeat + release | Stale token fails closed |
| State | Namespaced checkpoints | cursor/watermark/partition/snapshot |
| Effects | Normalized statuses; unknown fail-closed | No auto-retry without evidence |
| Preview | TTL, quota, staleness, shadow non-authority | Promotion SoD → **0.42** |
| CP3 vs GA | CP3 ≠ production multi-tenant | Graduation remains **0.43** |

## Open findings

Open **P0 count is 0**. Deferred P1 rows below are non-blocking for the 0.41
tag/publish rehearsal; they do not reopen ADR-018 locked dispositions.

| ID | Severity | Owner | State | Summary | Evidence / disposition |
|---|---|---|---|---|---|
| `041-P1-01` | P1 | Control-plane | Deferred | Fully normalize durable tables out of the versioned snapshot blob | Mitigation: optimistic `payload_version` + `FOR UPDATE` on reference snapshot provider; target **0.42** schema evolution if needed |
| `041-P1-02` | P1 | Control-plane + FastAPI | Deferred | Full DurableWorkStore HTTP surface (effects / repair / diagnose / shadow) | Mitigation: SDK protocol is authoritative; CONTROL_PLANE_API documents shipped routes only; target **0.42** if adopter demand warrants |

## Soft-continue from prior phases

| ID | Severity | Owner | State | Summary | Evidence / disposition |
|---|---|---|---|---|---|
| `038-X-01` | P1 | Ecosystem + echo maintainer | Soft-continue | Independent echo connector on PyPI | Non-blocking for CP3; see [FINDINGS_0_40](FINDINGS_0_40.md) |

## Closed in post-0.41.0 hardening (version remains 0.41.0; no tag yet)

| ID | Severity | Owner | State | Summary | Evidence / disposition |
|---|---|---|---|---|---|
| `041-H-01` | P1 | Control-plane | Closed | Checkpoint CAS required fencing (`attempt_id` + `fencing_token`) | `durable_memory.compare_and_swap_checkpoint`; FastAPI `DurableCheckpointCasBody`; ADR-018 |
| `041-H-02` | P1 | Control-plane | Closed | Cancel expires leases; heartbeat/CAS fail under `cancel_requested` | `cancel_submission` / `heartbeat` / CAS guards |
| `041-H-03` | P1 | FastAPI | Closed | Dual-write cancel is durable-first; invalid `submission_id` fails closed | `routes.cancel_run` + `_resolve_run_submission_id` |
| `041-H-04` | P1 | FastAPI | Closed | Dual-write submit compensates CP1 when durable accept fails after create | `routes.submit_run` |
| `041-H-05` | P1 | Control-plane | Closed | `input_snapshot` / replay diffs / preview `stale_reason` redacted on wire | `durable_models.to_dict` + accept-time redact |
| `041-H-06` | P1 | Runtime | Closed | Secret / Safe I/O failures cannot CONTINUE/SKIP | `orchestrator._is_security_hard_failure` |
| `041-H-07` | P1 | CLI | Closed | Human/JSON diagnostic paths use secret-safe serialization | `cli/output.py`, doctor/core/compile |
| `041-H-08` | P2 | Safe I/O | Closed | Wire `0` for max_read_bytes / lock_timeout is honored | `io_policy._wire_nonneg_*` |
| `041-H-09` | P2 | SQLModel | Closed | Pure durable reads use `_read_only` (no false `payload_version` bumps) | `durable_stores.explain/replay/plan_*` |
| `041-H-10` | P2 | FastAPI | Closed | Validate/plan profile resolution fail-closed (`allow_adhoc_profile=False`) | `_profile_meta` |

## Closure rules

1. Every P0 requires a regression test and linked durable evidence before
   severity can move or the finding can close.
2. Deferred P1 rows must name owner, target phase, mitigation, and
   non-blocking rationale.
3. Do not reopen ADR-018 locked dispositions without a written finding and
   migration plan.
