---
status: Available — 0.41 CP3
---

# Durable Submission and State (CP3)

The 0.41 control-plane foundation separates acceptance from execution. An
accepted submission creates an immutable submission record and an outbox record
in one provider transaction; dispatchers publish the outbox after commit.
Execution hosts lease a submission before starting an attempt, and every host
write carries a monotonically increasing fencing token.

Durable providers expose paginated `list_execution_scopes(ctx, limit=...,
after_submission_id=...)` for managed artifact retention. Each call returns a
bounded page of unique, complete authority contexts plus a cursor for the next
page. The SQLModel provider uses a bounded keyset query over the normalized
submission mirror. The execution host rotates that cursor across ticks, so
retention eventually visits completed submissions without loading the full
SQLModel snapshot. Within each tick, scopes that share a retention store are
deduplicated. A bounded retry queue revisits scopes whose cleanup failed or
reported more candidates, even while discovery continues through later pages.
Adapters with retention disabled skip scope discovery. SQLModel migration
`013_durable_submission_scope_backfill_0_56` backfills normalized submission
rows from existing snapshots before workers rely on the keyset pages.

## State-machine invariants

- Idempotency is scoped by tenant, workspace, operation, and the authenticated
  issuer-qualified principal. A key may be replayed only with the same immutable
  submission inputs.
- A cancellation request prevents new leases and attempts. Once an attempt
  acknowledges it, the submission is terminally `cancelled`; completed, failed,
  and cancelled submissions cannot be leased again.
- A submission has at most one running attempt. The attempt must hold the
  current lease and fencing token for every terminal write or checkpoint.
- Replay can select a workspace checkpoint only when it is global or belongs to
  the source submission. A checkpoint owned by another submission is rejected.
- Preview expiry must be in the future at creation time. Cleanup is reserved for
  previews that expire after they were successfully recorded.

`etlantic.control_plane.DurableWorkStore` is the provider contract. Its
`MemoryDurableWorkStore` implementation is suitable for local development and
conformance tests; production deployments must use a transactional provider.
The public records contain opaque IDs and fingerprints only—never resolved
secrets, source rows, or effect payloads.

Checkpoint advancement uses compare-and-swap. A checkpoint tied to an attempt
also requires the current, unexpired lease token, so a stale or terminal
attempt cannot advance durable state. Worker outcome effects use
`record_attempt_effect`, which checks the exact running attempt and its live
lease in the same store transaction as the effect write. A stale attempt cannot
replace committed or unknown recovery evidence. External effects may be
recorded as `unknown`; that is deliberately not an automatic-retry signal.
Reconciliation or idempotency evidence is required before a provider may safely
repeat it.

Replay returns the immutable plan, revision, plugin, policy, input snapshot,
and optional checkpoint selection used by the source submission. Preview
workspaces are tenant/workspace scoped, require distinct base and candidate
revisions, have a positive quota, and clean up only themselves after expiry.

## Minimal local example

```python
import etlantic as etl

store = etl.control_plane.MemoryDurableWorkStore()
submission, created = store.accept(
    ctx,
    idempotency_key="deploy-2026-07-31",
    operation="run.submit",
    plan_fingerprint="sha256:...",
    revision_id="revision-42",
)
for message in store.pending_outbox(ctx):
    # Publish `message` to a broker, then record the publication.
    store.mark_published(ctx, message.outbox_id)
```

The provider, not the API process, owns dispatcher and execution-host lifetime.
Optional FastAPI hosts may inject ``DurableWorkStore`` and expose
``/v1/durable/*`` routes; CP1 ``SubmissionStore`` receipts remain unchanged.
Optional SQLModel persistence applies migration ``002_durable_cp3``.
**CP3 ≠ production multi-tenant** (**0.43**).
