---
title: ETLantic 0.59 Exit Gate
status: candidate
current_minor: "0.59"
---

# ETLantic 0.59 Exit Gate — Managed Runtime Consolidation and Trigger Contracts

**Release decision: NOT READY TO TAG OR PUBLISH.** The 0.59 implementation
work and release metadata are present, but the required qualification evidence
has not been collected. The latest published and supported line remains
0.57.x.

## Release blockers

The [implementation plan](IMPLEMENTATION_PLAN_0_59.md) defines AC059-001–011
and evidence families E059-OWN, E059-MIG, E059-WIRE, E059-OCC, E059-SEC,
E059-REC, and E059-REL. Their release status is:

| Gate | Required evidence | Status |
|---|---|---|
| A–C | Settings parity, complete persistence compatibility, installed headless/HTTP/Prefect behavior, lifecycle and restart evidence | Pending |
| D | Independent wire consumer, malformed/version-skew corpus, auth and replay behavior, schedule lifecycle fixtures | Pending |
| E | Independent receiver/worker, process-loss recovery, concurrent admission and uncertain-effect evidence over real stores | Pending |
| F | All phase evidence indexed; supported matrix, migration report, unchanged 0.58 qualification, and release decision | Pending |

Static lint, formatting, and compilation checks alone do not satisfy these
gates. Before changing this decision, attach each evidence result with source
revision, package and dependency versions, store/process topology, and an
immutable artifact reference. Required skips or unavailable environments
remain blockers.

## Release preparation

- [x] Synchronize core and first-party distribution versions at 0.59.0.
- [x] Refresh the lockfile, plugin manifest digests, and generated versioned
  evidence bundles.
- [x] Add candidate notes, migration guidance, and this exit gate.
- [x] Pass the local release checks and build all 25 first-party distributions.
- [ ] Complete and index E059-OWN/MIG/WIRE/OCC/SEC/REC/REL evidence.
- [ ] Verify the release change is merged to `main` and the checkout is clean.
- [ ] Re-run release readiness on the exact release commit; then tag `v0.59.0`.

No tag, publish, or support-line change is authorized by this preparation
record. See the [release process](RELEASE_PROCESS.md) for the publishing
sequence.
