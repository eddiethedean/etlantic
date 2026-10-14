---
title: ETLantic rsconnect Integration Plan
description: Optional Posit Connect schedule adapter targeting compatible HTTPS receivers.
plan_status: implementation_complete_qualification_deferred
plan_last_reviewed: 2026-10-13
---

# ETLantic rsconnect Integration Plan

**Status: preview package implementation complete; production qualification is
deferred; phase [0.60](IMPLEMENTATION_PLAN_0_60.md).** The optional package may
be distributed after its repository-local checks pass. No Connect support tuple
or live acceptance gate is qualified, and neither is required for preview
distribution. Source provenance and the four-plan sequence are recorded in the
[runtime plan](ETLANTIC_RUNTIME_PLAN.md).

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
The reference uses static-batch `/1`, real PostgreSQL and separately installed
receiver/worker processes. Relevant deferred qualification from the
[0.59 exit gate](EXIT_GATE_0_59.md) carries forward; a published wire contract
does not establish live transport or recovery support.

Connect owns the timer and trigger process. The receiver durably admits work;
an independent executor runs the pipeline. Connect content contains no ETL
pipeline implementation or source/sink credentials. Direct pipeline execution
on Connect is outside this phase. `etlantic-quarto` does not exist and must not
be created or planned.

## Platform Facts And Qualification Decisions

Official documentation reviewed on 2026-10-13 establishes the following platform
constraints, not a qualified ETLantic support tuple:

- Python scripts use Quarto rendering and `rsconnect-python` publishing.
  Quarto/Jupyter and deployment-tool prerequisites belong in the exact build/
  server matrix. See [Posit's script guide](https://docs.posit.co/connect/user/scripts/index.html).
- Source-based rendered content is schedulable; interactive applications do not
  supply this timer topology. Deployment can render content, and refresh can run
  it manually. See [Posit's scheduling guide](https://docs.posit.co/connect/user/scheduling/).
- The Python SDK describes one schedule per variant and marks schedule mutations
  experimental. See [Posit's schedule SDK reference](https://posit-dev.github.io/posit-sdk-py/reference/connect.schedules.html).
- The public API documents schedule observation/history; that alone does not
  establish stable create/update/pause/resume/delete operations. See the
  [Connect API reference](https://docs.posit.co/connect/api/).

D060-API must select a vendor-supported stable lifecycle path or record explicit
preview/deferral scope before activation. Experimental SDK methods cannot silently
become production support. Manual dashboard configuration can characterize a
pilot but does not satisfy automated lifecycle acceptance. Map each adapter
operation to a real platform primitive; render-output activation must not be
mistaken for a timer pause control.

The first candidate is one Python/Quarto script and default variant, one owned
content item per registered schedule, one UTC interval and one explicit HTTPS
receiver, initially characterizing `fire_once` for delayed delivery. The current
receiver's `skip` policy skips a new arrival after its nominal time without an
implicit grace period. Only advertise recurrence/policy combinations whose
nominal sequences and live behavior match ETLantic's canonical clock. Local
timezone/DST, misfire, overlap and start/end semantics need separate rows;
arbitrary cron, multiple variants or shared content cannot be inferred from a
successful interval pilot.

The scheduled-invocation/nominal-slot decision is an activation blocker. A task's
actual start time, a mutable next-run value or process-local storage is not a
stable occurrence source. Qualify platform metadata or a durable mapping through
public runtime/store seams before sending. Build, deploy, preview, manual refresh
and rollback without a bound authorized occurrence must submit no work. Disable
deployment rendering where possible and qualify caching/output/redaction behavior.

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
  qualify a durable mapping mechanism or keep that mode inactive.
- Consume the implemented public 0.59 envelope/receipt `/1` schemas and exact
  occurrence algorithm, 16 KiB request bound, canonical UTC time, registered
  next-fire cursor and external timer-owner generation. Preserve nominal time
  and semantic identity when a retry arrives after the cursor advances. Scope
  comes from trusted authenticated context, never body fields.
- Bounded HTTPS delivery using shared outbound policy/conformance for destination,
  redirects, timeout, byte budgets and redaction; provider auth/request construction
  and delivery-specific retries stay here. Test actual DNS/connect behavior and
  explicit trusted private deployments. Include response validation, backoff,
  replay protection, and retry classification. A receipt is admission evidence,
  not pipeline completion; validation/auth failures must not retry forever.
- Classify accepted/skipped 200 receipts, pending-preparation 202, ambiguous
  response loss and permanent rejection separately. Validate correlation and
  schema before recording admission, constrain status references to authorized
  receiver policy, and reconcile uncertainty without generating a new occurrence.
  A receipt may precede run-ID allocation; pending is not accepted. Freeze one
  combined elapsed-time/attempt ceiling for platform and HTTP delivery retries.
- Schedule/content ownership records, drift inspection, failed-delivery status,
  scoped cleanup, and lifecycle runbooks. Updating or deleting content must not
  accidentally alter another application's schedule or cancel an accepted run.
- Journal remote mutation intent through public durable seams, verify ownership
  by scoped immutable references rather than names, and reconcile lost create/
  deploy responses before retrying. Pause/delete deny new canonical admissions
  before stopping the timer. Updates and rollback use new revisions/generation
  fencing; they cannot revive invalidated bindings. External drift and ambiguous
  remote resources require explicit reconciliation before mutation.

## Preview Package Release Acceptance

The release bar is entirely repository-local:

1. Build/install the optional wheel and import its public API without requiring a
   Connect server, Quarto, FastAPI, Data Mover, PostgreSQL, or receiver/worker.
2. Pass the focused package and inherited contract tests, lint, type checks,
   lockfile validation, wheel build, and strict documentation build.
3. Verify deterministic bundle generation and its manifest, absence of secret
   values, and fail-closed delivery when trusted occurrence context is absent.
4. Document schedule mutations as experimental and generated trigger delivery as
   inactive without a trusted occurrence-context provider; make no live or
   production support claim.

These checks permit a preview package release without an external platform,
maintainer decision, production receiver, or live acceptance campaign.

The [local simulation design](CONNECT_SIMULATION_DESIGN_0_60.md) defines pinned
SDK contract tests, deterministic faults, local HTTPS, and process-recovery
coverage. It records a confirmed SDK readback normalization defect and a
prioritized scenario matrix; the proposed tests have not yet been implemented.

## Deferred Production Support Qualification

Production support requires separately completing the applicable evidence below.
These items govern activation and support claims; they are not release gates for
the preview package.

1. A clean installation sends a qualified trigger to a non-FastAPI receiver
   without installing FastAPI or Data Mover.
2. Duplicate concurrent requests, receiver response loss, trigger restarts, and
   platform retries retain one occurrence/run mapping.
3. Unsupported recurrence and ambiguous occurrence identity fail before schedule
   activation; scheduling semantics are covered by a live compatibility corpus
   and an explicit API stability/support decision.
4. API restarts after acceptance do not lose work. Failed ETL is visible through
   the receiver's canonical status even if Connect reports trigger success.
5. Expired/revoked credentials, forbidden origins, redirects, TLS errors, and
   malformed/oversized responses produce bounded redacted failures.
6. Live isolated Connect deployment proves creation, scheduled delivery, update,
   pause/resume, rollback, reconciliation, and deletion with no orphan resources.
   Lost mutation responses, concurrent operators, external drift and partial
   failure recover safely. Deployment/manual refresh submit no unbound work.
7. Bundle and log inspection finds no source rows, source/sink secrets, complete
   pipeline definitions or credential values; clean generated-content installation
   does not pull ETL engines, stores or the complete provider environment.
8. One explicit-URL topology has installed/live evidence and all unsupported
   content, recurrence and hosting combinations are listed. A shared optional HTTP
   wheel is considered only after two real clients adopt it and remove duplication.

Publish exact Connect, Python, deployment-tool, content-type, auth, and recurrence
support matrices before making live support claims; fake/API fixture coverage
alone does not qualify Connect. Platform maintainers own content topology,
occurrence derivation, and recurrence translation decisions before the first
live pilot. Review on platform API or contract changes. The
[implementation plan](IMPLEMENTATION_PLAN_0_60.md) owns ordered production
qualification stages, D060 decisions and E060 evidence mapped to AC060-001–006;
unavailable/deferred cases remain unqualified without blocking preview package
distribution. A preview or manual pilot cannot close production lifecycle gates.
Endpoint auto-discovery belongs to the
optional application integration in
[0.62](ETLANTIC_DATA_MOVER_INTEGRATION_PLAN.md), not this package.
