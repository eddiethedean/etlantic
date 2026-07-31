---
status: Experimental — 0.41 CP3 foundation
---

# Durable Submission and State (CP3)

The 0.41 control-plane foundation separates acceptance from execution. An
accepted submission creates an immutable submission record and an outbox record
in one provider transaction; dispatchers publish the outbox after commit.
Execution hosts lease a submission before starting an attempt, and every host
write carries a monotonically increasing fencing token.

`etlantic.control_plane.DurableWorkStore` is the provider contract. Its
`MemoryDurableWorkStore` implementation is suitable for local development and
conformance tests; production deployments must use a transactional provider.
The public records contain opaque IDs and fingerprints only—never resolved
secrets, source rows, or effect payloads.

Checkpoint advancement uses compare-and-swap. A checkpoint tied to an attempt
also requires the current, unexpired lease token, so a stale or terminal
attempt cannot advance durable state. External effects may be recorded as
`unknown`; that is deliberately not an automatic-retry signal. Reconciliation
or idempotency evidence is required before a provider may safely repeat it.

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
