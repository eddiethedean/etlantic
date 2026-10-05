---
title: ETLantic 0.56 Standalone Compatibility Reset
description: Remove pre-0.56 runtime compatibility paths and qualification burden.
plan_status: current
plan_last_reviewed: 0.56.0-candidate
---

# ETLantic 0.56 Standalone Compatibility Reset

This plan narrows the 0.56 release contract to canonical 0.56 inputs, packages,
and persisted state. It is an execution overlay on the
[0.56 execution plan](EXECUTION_PLAN_0_56.md): all backend delivery work remains
in force, while the old-version upgrade requirements below replace its
compatibility-specific migration requirements. It also updates the
[implementation contract](IMPLEMENTATION_PLAN_0_56.md).

## Objective

Ship 0.56 with one supported model per current surface. Runtime and CLI paths
must not detect, rewrite, infer, or replay pre-0.56 forms. Old data must fail
closed with an actionable version error before execution, provider access, or
ownership decisions occur.

0.56 continues to support its current public SDK, `/1` plugin families, current
wire schemas, independently authored private plugins, and current security and
capability checks. This plan removes historical input compatibility; it does
not remove compatibility guarantees within the declared 0.56 ecosystem.

## Release boundary decision

Adopt a clean 0.56 state boundary. Existing 0.55 profiles, requests, plans,
reports, database rows, leases, receipts, and accepted work are not read by the
0.56 runtime. Deployments must start with a fresh 0.56 store or use a separately
run, explicit migration/export tool if continuity is required. The runtime
does not contain dual-read logic. In particular, do not use subject-only owner
fallbacks for 0.55 input resources.

Before implementation, the release owner records whether an offline converter
is in scope. If it is, that tool writes only canonical 0.56 state, runs outside
the online request/worker path, and has its own dry-run, backup, integrity, and
rollback evidence. Without that decision and evidence, the supported path is a
fresh 0.56 store.

## Ordered work

| Step | Work | Exit evidence |
|---|---|---|
| 0 — Freeze boundary | Update support/deprecation policy; list accepted 0.56 encodings, package versions, schemas and durable record versions; decide fresh-store versus offline converter | Reviewed compatibility inventory; no ambiguous 0.55 upgrade promise |
| 1 — Remove authoring fallbacks | Remove `Profile.bindings` and JSON alias handling, `--accept-legacy-bindings`, `profile migrate`, implicit ad hoc profile options, and schema-less plan decode/fallback-to-pipeline behavior | Canonical profile/project/CLI flows work; removed flags and old forms produce direct errors |
| 2 — Make decoders canonical | Remove report metadata alias rewriting, missing `explicit_settings` inference, legacy intent-key lookup, stream envelope/state migration adapters, and old aggregate compiler-finding normalization where applicable | Each public decoder accepts its documented 0.56 shape only; malformed/old shapes fail with a stable diagnostic |
| 3 — Remove durable-state fallback | Remove legacy run-ID derivation, legacy artifact ownership resolution, missing-envelope recovery branches, old input-resource lease-scope matching, and durable-store idempotency fallback | Old rows are rejected before replay, worker claim, artifact lookup, lease acquisition, or provider I/O; current 0.56 crash recovery still passes |
| 4 — Prune compatibility gates | Remove old-version codec burn-in matrices, obsolete release fixtures, legacy-only regression tests, and CI/doc checks that require removed flags or historical readers | CI no longer installs/tests old core/plugin releases for a 0.56 support claim; current-version conformance, security, migration-chain and isolation checks remain |
| 5 — Publish boundary | Update migration/support/compatibility docs, schemas and package qualification records; publish clean-store and rollback requirements | Built 0.56 distributions install and initialize cleanly; release documents clearly state the 0.55 state boundary |

### Step 0 inventory

Treat these as initial inventory anchors, then search for all callers and
fixtures before deletion:

- Profiles and CLI: `src/etlantic/profile.py`, `src/etlantic/project.py`,
  `src/etlantic/cli/globals.py`, `src/etlantic/cli/context.py`,
  `src/etlantic/cli/cmds/profile.py`, and profile-bearing CLI commands.
- Plans and reports: `src/etlantic/cli/cmds/core.py`,
  `src/etlantic/reports/model.py`, `src/etlantic/reports/upgrade.py`, and
  `src/etlantic/extensions.py`.
- Requests, streaming, and compilers: `src/etlantic/runtime/request.py`,
  `src/etlantic/streaming/migration.py`, `src/etlantic/streaming/__init__.py`,
  `src/etlantic/transform/compiler.py`, and
  `src/etlantic/transform/capabilities.py`.
- Managed state: `src/etlantic/runtime/managed_execution.py`,
  `src/etlantic/service/managed.py`, `src/etlantic/control_plane/`, and the
  SQLModel provider's migration and receipt lookup paths.
- Gates and records: `scripts/check_pipeline_codec_burn_in.py`,
  `scripts/check_isolated_codec_burn_in.py`, `scripts/check_docs.py`,
  `.github/workflows/`, `tests/compatibility/`, and
  `tests/fixtures/burn_in/`.

## Required invariants

1. No old payload is silently normalized into a 0.56 object.
2. No old accepted command is resumed or replayed by 0.56.
3. Version rejection occurs before secrets, plugins, provider I/O, artifact
   reads, owner fallback, or state mutation.
4. Current 0.56 retries, concurrency fencing, idempotency, cancellation,
   unknown-commit handling, and result-publication recovery remain supported.
5. Removing compatibility does not weaken authorization, tenant isolation,
   secret handling, plugin allowlists, schema validation, or capability checks.
6. Historical migration documents may remain as archival records, but current
   docs and automated checks must not imply those old forms are accepted.

## Acceptance criteria

- **CR-1 Canonical authoring:** profile, project, request, plan, report, and
  stream inputs either conform to the current documented shape or fail clearly.
- **CR-2 No old-state execution:** fixture records from the 0.55 line cannot be
  accepted, claimed, replayed, resumed, or used to resolve artifact ownership.
- **CR-3 Current recovery preserved:** fresh 0.56 records recover correctly at
  each existing durable acceptance, effect, and publication boundary.
- **CR-4 No historical CI contract:** the required CI suite contains no
  old-version reader/writer matrix, old wheel install, or old-format golden
  verification for 0.56.
- **CR-5 Current ecosystem intact:** matched 0.56 first-party packages,
  current plugin protocols, third-party conformance, and private plugins remain
  qualified against their declared 0.56 contracts.
- **CR-6 Security unchanged:** fail-closed plugin/resource/schema allowlists,
  scoped identity, redaction, and secret-free persistence remain release gates.
- **CR-7 Recovery instructions:** operators can distinguish a rejected old
  store from corruption and are given the supported fresh-store or offline
  conversion path, including backup and rollback limits.

## Release qualification

Replace upgrade-from-0.55 qualification with these checks:

- Fresh 0.56 install and initialization from an empty store.
- Deterministic rejection of representative 0.55 profiles, requests, reports,
  accepted submissions, resource ownership records, and database state before
  execution or mutation.
- Restart, concurrency, replay, retention, and publication-recovery
  qualification using only canonical 0.56 state.
- Clean-wheel installation and matched-version first-party plugin/provider
  qualification.
- If an offline converter is approved, separate converter qualification and a
  documented restore rehearsal; do not make it a runtime fallback.

Do not remove present-day safety or correctness gates merely because they are
called compatibility checks. Contract/model write compatibility, plugin trust,
security allowlists, schema validation, engine capabilities, current package
matching, and the SQLModel migration chain for fresh 0.56 stores remain required.
