---
title: Migration from ETLantic 0.55 to 0.56
status: candidate
current_minor: "0.56"
---

# Migration from 0.55 to 0.56

> **Status: 0.56.0 is a qualification candidate and is not published.**

## Candidate package line

Core and first-party distributions are qualified together at `0.56.0`; plugin
metadata requires `etlantic>=0.56.0,<0.57`. Do not mix 0.55 and 0.56
first-party packages in one environment. The published and
supported line remains 0.55.x until the candidate passes final release review
and is published.

## Partition repair and backfill

PostgreSQL partition actions require the provider binding to specify
`partition_column` and the operator profile to allow the required partition
read, replacement, and idempotency capabilities. Selectors are validated
before execution. The provider reads within the selected partitions and
replaces those partitions atomically with the effect record. An empty result
clears the selected partitions.

Existing non-partitioned pipelines need no configuration change. Other providers
remain unavailable for these actions until they advertise and implement the
required capabilities. Repair/backfill uses the normal managed authorization,
command identity, status, attempt and lineage surfaces.

## Managed recovery and quota providers

Scheduled occurrences recover their accepted execution envelope before resolving
external parameter references again. Recovery repairs partial acceptance and
rechecks submission authorization before linking the original firing.

Custom quota providers must return `metadata.reservation_key` for keyed allowed
admissions and support idempotent releases using `<reservation_key>:release`.
Retries share an active reservation. Once released, the same command must pass
admission again and receive a fresh reservation identity so an earlier release
cannot affect its new usage. The SQLModel provider persists both identities and
release acknowledgements. Managed run submission passes a unique `claim_id` to
`admit` for each submission attempt. Compensating `release` with that `claim_id`
must abandon only that attempt and decrement usage only when no owners remain.
Terminal worker releases omit `claim_id` and release the whole reservation.
Claims and their abandonment must be atomic and durable alongside admission so
overlapping submitters on different service instances cannot uncharge each other.
The SQLModel snapshot writer checks its version in the database update; a
stale concurrent writer receives a conflict without replacing another claim.
CP1-only replay checks that the run is still accepted and the original quota
reservation is still active before restoring durable work. A compensated run
receipt cannot be replayed after its quota has been released.

Custom durable work providers must support `pending_outbox(include_terminal=True)`,
`pending_outbox(terminal_only=True)` (filtering before applying the page limit),
and `reconcile_cancelled_submissions(acknowledge_outbox=False)`. The execution
worker uses these options to retain cancelled work until quota release succeeds;
defaults preserve existing dispatcher behavior. Custom execution hosts must pass
their quota provider to `ExecutionHost(quota_provider=...)`. The standard managed
backend configures this automatically.

See [What's new in 0.56](../01_GETTING_STARTED/WHATS_NEW_0_56.md) and the
[phase qualification record](evidence/phase_0_56/LOCAL_QUALIFICATION.md).
