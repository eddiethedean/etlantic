---
title: ETLantic 0.57 Exit Gate
status: candidate-qualification
current_minor: "0.57"
---

# ETLantic 0.57 Exit Gate — Managed Backend Independence and Runtime Supervision

**Release decision: pending candidate qualification.** This page is the release
checklist for issues #278–#282. Do not tag or publish `v0.57.0` until every
release-blocking item below has a passing, commit-matched observation.

## Scope

0.57 delivers one authorized headless backend graph, transport-independent
schedule commands, explicit managed scheduler collaborators, provider-owned
read-only SQLModel schema inspection, and local status/cooperative drain for
scheduler and worker roles. The existing FastAPI surface remains an adapter.

No new migration is introduced. The existing migration head is
`014_cp1_complete_principal_idempotency_0_56`; deployed databases at that head
must inspect as compatible. Migration and persisted-format compatibility are
covered by the SQLModel migration suite and the live provider qualification.

## Acceptance evidence

| Acceptance | Required evidence | Status |
|---|---|---|
| I278-H: headless construction | Exact core and SQLModel wheels in an isolated environment without FastAPI; authorized schedule operation; all three role factories and ticks | Pending candidate wheels |
| I278-G: adapter and import boundary | Fresh-process import checks; compatibility adapter and shared service graph; worker execution modules remain lazy | Pending candidate run |
| I278-L: lifecycle ownership | Owned/borrowed engine behavior, partial construction, repeated close, and active-work close safety | Pending candidate run |
| I279-P: command parity | Schedule service and HTTP route authorization, read filtering, revisions, conflicts, and canonical records | Pending candidate run |
| I279-R: retry and authorization races | Duplicate trigger, response loss, stale revision, scope denial, and interrupted-link recovery | Pending candidate run |
| I280-M: managed scheduler wiring | Shared schedule store and explicit prepare/submit/recover collaborator; no implicit managed recovery | Pending candidate run |
| I280-C: durable PostgreSQL recovery | Independent scheduler processes and restart recovery for accepted, unlinked firings | Pending live PostgreSQL evidence |
| I281-S: schema state matrix | Fresh, behind, compatible, unknown/ahead, corrupt/partial, and unreachable public results; no DDL or commit | Local SQLite tests added; candidate CI pending |
| I281-P: least privilege | Restricted PostgreSQL role without schema CREATE; read-only inspection/construction and useful runtime DML | Candidate live PostgreSQL evidence pending |
| I282-T: status and drain | Idle/active/standby, repeat drain, stop/claim races, outage, recovery, and lease loss across all roles | Unit contract tests added; candidate CI pending |
| I282-X: shutdown and recovery | Grace expiry, in-flight work, process death/restart, fencing, no synthetic completion, and no early engine disposal | Pending candidate run |

The current workflow has dedicated 0.57 acceptance and installed-wheel jobs. Its
JUnit and wheel qualification artifacts must be linked here after the final
candidate commit. The local installed-wheel record is
[`evidence/phase_0_57/LOCAL_HEADLESS_WHEEL_QUALIFICATION.json`](evidence/phase_0_57/LOCAL_HEADLESS_WHEEL_QUALIFICATION.json);
it qualifies source at commit `cb0518f1` with 0.56.2-versioned wheels and is
development evidence only, not a substitute for candidate-wheel results.

## Release checks

- [ ] Every required acceptance row above has passing commit-matched evidence.
- [ ] A clean candidate build produces lockstep 0.57.0 core and first-party wheels.
- [ ] Core and SQLModel installed-wheel qualification passes with FastAPI absent.
- [ ] Supported Python 3.11–3.13 matrix, SQLModel, FastAPI, and real PostgreSQL CI pass.
- [ ] Schema inspection and normal backend construction perform no DDL or explicit commit.
- [ ] Migration guide, release notes, API docs, changelog, release facts, manifests, and lockfile agree.
- [ ] `scripts/check_release.py`, plugin manifest checks, docs checks, and strict docs build pass for 0.57.0.
- [ ] Issues [#278](https://github.com/eddiethedean/etlantic/issues/278) through [#282](https://github.com/eddiethedean/etlantic/issues/282) link to passing acceptance evidence before closure.

## Decision

**NO-GO until all boxes and acceptance rows pass.** A green generic CI run does
not replace exact-wheel, live PostgreSQL, or issue-specific evidence. Update the
decision and evidence links only after the final candidate commit is qualified.
