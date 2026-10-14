---
title: ETLantic 0.59 Exit Gate
status: published
current_minor: "0.59"
---

# ETLantic 0.59 Exit Gate — Managed Runtime Consolidation and Trigger Contracts

**Release decision: 0.59.0 Beta published on 2026-10-14 with external
qualification deferred.** The campaigns below remain open, are not represented
as passed, and do not qualify the managed runtime consolidation or external
trigger additions for production use. The separate release decision authorized
publication while retaining this qualification deferral.

## Deferred external qualification

The [implementation plan](IMPLEMENTATION_PLAN_0_59.md) defines AC059-001–011
and evidence families E059-OWN, E059-MIG, E059-WIRE, E059-OCC, E059-SEC,
E059-REC, and E059-REL. All external acceptance campaigns in those families
are deferred from the 0.59 exit and carried forward for later qualification.
The detailed cases and required environments remain in the implementation
plan; this decision records deferral, not completion.

| Gate | Required evidence | Status |
|---|---|---|
| A–C | Settings parity, complete persistence compatibility, installed headless/HTTP/Prefect behavior, lifecycle and restart evidence | Deferred from 0.59; retain requirements and do not claim external qualification |
| D | Independent wire consumer, malformed/version-skew corpus, auth and replay behavior, schedule lifecycle fixtures | Deferred from 0.59; retain requirements and do not claim external qualification |
| E | Independent receiver/worker, process-loss recovery, concurrent admission and uncertain-effect evidence over real stores | Deferred from 0.59; retain requirements and do not claim external qualification |
| F | Evidence index, supported matrix, migration report, unchanged 0.58 qualification, and release decision | Deferral recorded; exact-commit readiness remains open |

Static lint, formatting, compilation, and local CI checks do not satisfy the
deferred external campaigns. When qualification resumes, attach each result
with source revision, package and dependency versions, store/process topology,
and an immutable artifact reference. Required skips or unavailable environments
remain incomplete until the relevant evidence is supplied.

## Release preparation

- [x] Synchronize core and first-party distribution versions at 0.59.0.
- [x] Refresh the lockfile, plugin manifest digests, and generated versioned
  evidence bundles.
- [x] Add candidate notes, migration guidance, and this exit gate.
- [x] Pass the local release checks and build all 25 first-party distributions.
- [x] Defer external E059-OWN/MIG/WIRE/OCC/SEC/REC/REL campaigns from 0.59;
  retain their evidence requirements and do not mark them passed.
- [x] Merge the release change to `main`; verify the checkout is clean.
- [x] Pass release checks on exact commit
  `a787f91cf865dda06e59576625db0ad53bb7aa61` (CI run
  [38489366012](https://github.com/eddiethedean/etlantic/actions/runs/38489366012)).
- [x] Publish `v0.59.0` as a Beta release while keeping external qualification
  campaigns deferred.

The publication decision does not mark the deferred external qualification
campaigns as passed. Continue to hold the affected managed-runtime and external
trigger additions from production use until their evidence is completed. See
the [release process](RELEASE_PROCESS.md) for the publishing sequence.
