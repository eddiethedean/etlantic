---
title: ETLantic 0.59 Exit Gate
status: candidate
current_minor: "0.59"
---

# ETLantic 0.59 Exit Gate — Managed Runtime Consolidation and Trigger Contracts

**Release decision: EXTERNAL QUALIFICATION DEFERRED. NOT READY TO TAG OR PUBLISH
until the change is merged cleanly and exact-commit readiness passes.**
ETLantic 0.59 remains a Beta release candidate. The external qualification
campaigns below are deferred from the 0.59 exit. Their evidence remains open
and is not represented as passed. The latest published and supported line
remains 0.57.x.

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
- [ ] Verify the release change is merged to `main` and the checkout is clean.
- [ ] Re-run release readiness on the exact release commit and record a release
  decision before tagging `v0.59.0`.

The external evidence deferral does not authorize a tag, publish, or
support-line change. Complete the remaining merge and exact-commit readiness
steps before making a separate release decision. See the
[release process](RELEASE_PROCESS.md) for the publishing sequence.
