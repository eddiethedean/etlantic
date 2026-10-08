---
title: ETLantic 0.57 Exit Gate
status: release-ready
current_minor: "0.57"
---

# ETLantic 0.57 Exit Gate — Managed Backend Independence and Runtime Supervision

**Release decision: GO for `v0.57.0`.** Candidate source revision
[`94fe5c29`](https://github.com/eddiethedean/etlantic/commit/94fe5c29182c37ab9398146b61609cb6ebc9a59a)
passed the full CI matrix (run [37832487031](https://github.com/eddiethedean/etlantic/actions/runs/37832487031),
attempt 2) and the acceptance evidence below. ETLantic 0.56.2 remains the
published release until 0.57.0 is tagged and published.

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
| I278-H: headless construction | Exact core and SQLModel wheels in an isolated environment without FastAPI; authorized schedule operation; all three role factories and ticks | Pass — [installed-wheel evidence](https://github.com/eddiethedean/etlantic/actions/runs/37832487031/artifacts/11573943959) |
| I278-G: adapter and import boundary | Fresh-process import checks; compatibility adapter and shared service graph; worker execution modules remain lazy | Pass — [acceptance JUnit](https://github.com/eddiethedean/etlantic/actions/runs/37832487031/artifacts/11573704816) |
| I278-L: lifecycle ownership | Owned/borrowed engine behavior, partial construction, repeated close, and active-work close safety | Pass — [acceptance JUnit](https://github.com/eddiethedean/etlantic/actions/runs/37832487031/artifacts/11573704816) |
| I279-P: command parity | Schedule service and HTTP route authorization, read filtering, revisions, conflicts, and canonical records | Pass — [acceptance JUnit](https://github.com/eddiethedean/etlantic/actions/runs/37832487031/artifacts/11573704816) |
| I279-R: retry and authorization races | Duplicate trigger, response loss, stale revision, scope denial, and interrupted-link recovery | Pass — [acceptance JUnit](https://github.com/eddiethedean/etlantic/actions/runs/37832487031/artifacts/11573704816) |
| I280-M: managed scheduler wiring | Shared schedule store and explicit prepare/submit/recover collaborator; no implicit managed recovery | Pass — [acceptance JUnit](https://github.com/eddiethedean/etlantic/actions/runs/37832487031/artifacts/11573704816) |
| I280-C: durable PostgreSQL recovery | Independent scheduler processes and restart recovery for accepted, unlinked firings | Pass — live PostgreSQL cases in [acceptance JUnit](https://github.com/eddiethedean/etlantic/actions/runs/37832487031/artifacts/11573704816) |
| I281-S: schema state matrix | Fresh, behind, compatible, unknown/ahead, corrupt/partial, and unreachable public results; no DDL or commit | Pass — SQLite and PostgreSQL cases in [acceptance JUnit](https://github.com/eddiethedean/etlantic/actions/runs/37832487031/artifacts/11573704816) |
| I281-P: least privilege | Restricted PostgreSQL role without schema CREATE; read-only inspection/construction and useful runtime DML | Pass — live PostgreSQL cases in [acceptance JUnit](https://github.com/eddiethedean/etlantic/actions/runs/37832487031/artifacts/11573704816) |
| I282-T: status and drain | Idle/active/standby, repeat drain, stop/claim races, outage, recovery, and lease loss across all roles | Pass — [acceptance JUnit](https://github.com/eddiethedean/etlantic/actions/runs/37832487031/artifacts/11573704816) |
| I282-X: shutdown and recovery | Grace expiry, in-flight work, process death/restart, fencing, no synthetic completion, and no early engine disposal | Pass — [acceptance JUnit](https://github.com/eddiethedean/etlantic/actions/runs/37832487031/artifacts/11573704816) |

The acceptance artifact reports 160 passing tests with no failures or skips.
The installed-wheel artifact records aligned 0.57.0 versions, FastAPI absent,
and successful scheduler, run-worker, and action-worker construction and
operation. It includes the exact core and SQLModel wheel hashes. The CI run
completed all 45 jobs successfully on attempt 2. The older local installed-wheel
record is retained as historical development evidence only.

## Release checks

- [x] Every required acceptance row above has passing commit-matched evidence.
- [x] A clean candidate build produces lockstep 0.57.0 core and first-party wheels.
- [x] Core and SQLModel installed-wheel qualification passes with FastAPI absent.
- [x] Supported Python 3.11–3.13 matrix, SQLModel, FastAPI, and real PostgreSQL CI pass.
- [x] Schema inspection and normal backend construction perform no DDL or explicit commit.
- [x] Migration guide, release notes, API docs, changelog, release facts, manifests, and lockfile agree.
- [x] `scripts/check_release.py`, plugin manifest checks, docs checks, and strict docs build pass for 0.57.0.

Issues [#278](https://github.com/eddiethedean/etlantic/issues/278) through
[#282](https://github.com/eddiethedean/etlantic/issues/282) can now link to this
passing evidence when they are closed.

## Decision

**GO for release.** Tagging and publication remain separate release actions.
