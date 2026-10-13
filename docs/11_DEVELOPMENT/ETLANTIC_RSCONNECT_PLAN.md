---
title: ETLantic rsconnect Integration Plan
description: Optional Posit Connect schedule adapter targeting compatible HTTPS receivers.
plan_status: planned
plan_last_reviewed: 2026-10-12
---

# ETLantic rsconnect Integration Plan

**Status: planned; phase [0.60](IMPLEMENTATION_PLAN_0_60.md).** No
`etlantic-rsconnect` support is claimed by this plan. Source provenance and the
four-plan sequence are recorded in the [runtime plan](ETLANTIC_RUNTIME_PLAN.md).

## Outcome And Boundary

Deploy lightweight trigger content to Posit Connect, configure native scheduling,
and send the runtime HTTP trigger contract to an authorized, configured HTTPS
endpoint. The receiver can be FastAPI, Flask, Django, or another implementation.
`etlantic-rsconnect` consumes the shared public/wire contract, never depends on
`etlantic-fastapi`, `fastapi-posit`, or Data Mover, and reuses the existing outbound
policy. The [scope consolidation plan](PACKAGE_SCOPE_CONSOLIDATION_PLAN.md) applies.
The first qualification uses one selected script content type, one schedule per
owned content item, an explicit URL and one independent receiver/worker topology.
Other content/hosting combinations require demand and separate evidence.

Connect owns the timer and trigger process. The receiver durably admits work;
an independent executor runs the pipeline. Connect content contains no ETL
pipeline implementation or source/sink credentials. Direct pipeline execution
on Connect is outside this phase. `etlantic-quarto` does not exist and must not
be created or planned.

## Platform Facts And Qualification Decisions

Posit's documented script publishing path uses specially formatted Python
scripts rendered with Quarto and deployed with `rsconnect-python`. Thus a small
trigger script may require Quarto tooling in its build/runtime environment;
removing an ETLantic package proposal does not remove platform prerequisites.
Record exact tool versions and the selected content type in the compatibility
matrix. See [Posit script documentation](https://docs.posit.co/connect/user/scripts/index.html).

Use the supported Connect schedule API and reject recurrence semantics that
cannot be represented. Do not assume arbitrary cron or multiple independent
schedules with distinct parameters on one content item. Start with an explicit
schedule-to-content mapping; sharing content requires separate proof. Verify
timezone/DST, missed occurrences, overlap, schedule update, and task identity
against the [Connect API](https://docs.posit.co/connect/api/).

## Deliverables

- Public schedule adapter with versioned capability inspection and explicit
  create/read/update/pause/resume/delete/reconcile operations.
- Deterministic minimal trigger bundle using the wire contract without the full
  ETL engine/provider environment, pinned dependencies, manifest, scoped
  deployment ownership, and idempotent deployment/update/rollback handling.
- Explicit target URL and credential reference configuration, validated before
  publishing. Deployment credentials and runtime trigger credentials are distinct.
- Stable occurrence derivation preserved across retries and task restarts;
  intended scheduled time, content/schedule revision, and delivery-attempt
  identity remain separate. If Connect cannot supply sufficient metadata,
  qualify a durable mapping mechanism or reject that mode before release.
- Bounded HTTPS delivery using shared outbound policy/conformance for destination,
  redirects, timeout, byte budgets and redaction; provider auth/request construction
  and delivery-specific retries stay here. Test actual DNS/connect behavior and
  explicit trusted private deployments. Include response validation, backoff,
  replay protection, and retry classification. A receipt is admission evidence,
  not pipeline completion; validation/auth failures must not retry forever.
- Schedule/content ownership records, drift inspection, failed-delivery status,
  scoped cleanup, and lifecycle runbooks. Updating or deleting content must not
  accidentally alter another application's schedule or cancel an accepted run.

## Acceptance And Evidence

1. A clean installation sends a qualified trigger to a non-FastAPI receiver
   without installing FastAPI or Data Mover.
2. Duplicate concurrent requests, receiver response loss, trigger restarts, and
   platform retries retain one occurrence/run mapping.
3. Unsupported recurrence and ambiguous occurrence identity fail before schedule
   activation; scheduling semantics are covered by a live compatibility corpus.
4. API restarts after acceptance do not lose work. Failed ETL is visible through
   the receiver's canonical status even if Connect reports trigger success.
5. Expired/revoked credentials, forbidden origins, redirects, TLS errors, and
   malformed/oversized responses produce bounded redacted failures.
6. Live isolated Connect deployment proves creation, scheduled delivery, update,
   pause/resume, rollback, reconciliation, and deletion with no orphan resources.
7. Bundle and log inspection finds no source rows, source/sink secrets, complete
   pipeline definitions or credential values; clean generated-content installation
   does not pull ETL engines, stores or the complete provider environment.
8. One explicit-URL topology has installed/live evidence and all unsupported
   content, recurrence and hosting combinations are listed. A shared optional HTTP
   wheel is considered only after two real clients adopt it and remove duplication.

Publish exact Connect, Python, deployment-tool, content-type, auth, and recurrence
support matrices; fake/API fixture coverage alone does not qualify Connect.
Platform maintainers own content topology, occurrence derivation, and recurrence
translation decisions before the first live pilot. Review on platform API or
contract changes. Endpoint auto-discovery belongs to the optional application
integration in [0.62](ETLANTIC_DATA_MOVER_INTEGRATION_PLAN.md), not this package.
