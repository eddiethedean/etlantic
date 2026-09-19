# Migration from 0.53 to 0.54

This is a local implementation candidate; independent review/publication remain
pending. Upgrade core and first-party packages together to 0.54.0. Plugins depend
on `etlantic>=0.54.0,<0.55`; package ranges are not adaptive backend support ranges.
The adaptive campaign pins Polars 1.42.1, Pandas 2.3.3 and PyArrow 25.0.0.

Explicit remains the default, and ordinary `/1` plans gain no adaptive metadata.
Valid historical `/2` plans remain readable, but current version/evidence pins
can require replanning before execution. Stored `/2` is never rewritten or
downgraded to `/1`. No database or connector protocol migration is required.

New adaptive plans capture effective parameter values by node/name in
`metadata["etlantic.runtime"]["parameters"]`, after applying request overrides
and defaults. Admission checks that capture against the live request and
available authoring values before effects. Legacy parameterized `/2` plans
without the capture remain readable but require replanning for runtime
execution. Ordinary `/1` and historical `/2` wire serializers are unchanged;
effective values are carried in runtime metadata rather than added to legacy
parameter wire records.

The new source is opt-in through `create_parquet_storage()` and explicit runtime
registration. Only the exact five-node, fully placement-bound development/test
reference signature is eligible for fusion. New profiles should set
`portable_transform_policy="require"`. No general pushdown switch was added.
See [source restrictions and workspace binding](ADAPTIVE_0_54_USAGE.md).

## Finite recovery procedure

1. Stop application admission of new adaptive work; use explicit profiles for
   newly submitted work. A Profile edit alone does not revoke stored plans.
2. Quarantine externally queued stored `/2` plans without editing their bytes.
   Existing durable/control-plane workers already reject `/2`; no new queue or
   product kill switch is introduced.
3. Cancel or drain active tasks. Wait for native workers before releasing their
   immutable source buffers. The bounded Parquet adapter creates no disk
   snapshot artifacts or cleanup obligations. Its compatibility method
   `source.pending_snapshot_cleanups()` returns no tokens;
   `source.reconcile_snapshot_cleanup(cleanup_id)` rejects unknown tokens.
   Historical reports remain unchanged; draining does not authorize
   run/publication retries. Other runtime cleanup obligations still require
   reconciliation by their actual owners.
4. Reconcile PMADP524 uncertain publication receipts against the actual
   destination before retrying. Do not blindly retry, delete published output,
   or treat sink preparation as a commit.
5. Retain active checkpoints until drain. Invalidate stale references only under
   their recorded retention/security-domain policy; never cross tenant domains.
6. Repin the complete matching package set if rolling back. Replan explicit
   work from authoring definitions and verify the new `/1` plan. Never edit a
   stored physical `/2` plan into an explicit plan.

The qualification campaign exercises admission drift, cancellation/drain,
checkpoint/reuse, definite failure and acknowledgement-loss ownership. The
[reference example](ADAPTIVE_0_54_USAGE.md) is a finite process-local run.
