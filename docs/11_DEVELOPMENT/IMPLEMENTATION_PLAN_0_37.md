---
status: in-progress
since: "0.37.0"
current_minor: "0.37"
audience: maintainer
---

# ETLantic 0.37 Implementation Plan — Stable Foundation

> **Status: In progress.** ETLantic 0.37 is the current in-tree stable-foundation
> gate. This document does not claim PyPI publication or live immutable
> documentation. The
> [main roadmap](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md)
> owns release order, [Capabilities](../01_GETTING_STARTED/CAPABILITIES.md)
> owns shipped behavior, and `EXIT_GATE_0_37.md` owns release evidence.

## Outcome

Graduate ETLantic (and matching Medallantic) **0.37** as the stable foundation:
execute scheduled removals, graduate public application-pipeline testing,
prove acceptance scenarios **1–21**, publish a security verification matrix,
freeze stability claims for the foundation envelope, and rehearse release
against exact candidate artifacts.

0.37 is a graduation and freeze release. It is not a vehicle for broad new
product surface.

## Locked dispositions (from 0.36)

Carried forward from [FINDINGS_0_36](FINDINGS_0_36.md) and the 0.37 protocol
decision record. Do not reopen without a written finding and migration plan.

| Surface | Disposition for 0.37 |
|---|---|
| `etlantic.testing` | **Graduates** to the stable application-pipeline testing foundation |
| `etlantic.quality/1` | **Remains provisional** (outside the full stable-foundation claim) |
| `etlantic-datafusion` / DataFusion | **Remains experimental**; no Gate B graduation |
| Arrow interchange | **Gate A only** (Polars↔Pandas); no Gate B claim |
| Demoted root aliases (`_DEMOTED_ALIASES`) | **Removed** in 0.37.0 |
| `DataContractModel` alias | **Removed** in 0.37.0 |
| `etlantic.scheduler/1` | **Already stable MVP** (0.37); Prefect bounds unchanged |
| PyPI Beta classifier | **Retained** for core and first-party packages |

## Definition of done

The phase is complete only when all of the following are true:

1. Demoted root aliases and `DataContractModel` are removed with changelog,
   migration notes, and fail-closed import tests.
2. Public `etlantic.testing` graduates: isolated-wheel evidence, deterministic
   snapshots, and no private-core imports.
3. Acceptance suite items **1–21** have executable evidence (or an explicit
   `unsupported` / non-blocking disposition for experimental-only cells).
4. Every mandatory Security Model control has an owner, automated check, and
   residual-risk row in the security verification matrix.
5. Stability freeze inventories match the claimed public surface (API,
   protocols, diagnostics, schemas, CLI).
6. Release rehearsal passes against the exact candidate wheels, digests, and
   immutable docs path.
7. There are no unresolved P0 findings; every remaining P1 has owner, target
   phase, mitigation, and non-blocking rationale.
8. Documentation, migration guidance, and versioned Read the Docs pages are
   verified against the exact wheels users install.

## Authority and boundaries

When sources disagree, use this order:

1. Current-version capabilities, API, CLI, and package documentation define
   what ships.
2. The main roadmap defines milestone order and the 0.37 exit outcome.
3. This document defines the implementation sequence, evidence, and ownership
   for 0.37.
4. Domain plans define their own detailed semantics.
5. Tests, manifests, built wheels, release records, and the exit gate provide
   completion evidence.

Non-negotiable boundaries (unchanged from 0.36):

- ETLantic owns portable modeling, validation, deterministic planning, runtime
  coordination, evidence, and plugin contracts.
- Engine and orchestrator behavior remains in optional packages.
- Bronze, silver, and gold vocabulary remains in Medallantic.
- Plans, reports, diagnostics, snapshots, and test evidence must never contain
  resolved secret values.
- Production profiles require an explicit `plugin_allowlist` and fail closed.
- Schema-history and fixtures store schemas, fingerprints, and bounded
  metadata—not source rows.
- Airflow remains a compile target via `etlantic-airflow`.
- Experimental DataFusion behavior cannot graduate by assertion.

## Scope

### In scope

- Execution of [REMOVAL_CANDIDATES_0_37](REMOVAL_CANDIDATES_0_37.md) remainder.
- Application-pipeline testing foundation graduation.
- Stable-foundation acceptance suite **1–21** (see roadmap § 0.37).
- Security verification matrix and residual-risk register.
- Public-surface stability freeze for the foundation envelope.
- Exact-artifact release rehearsal (build, install, smoke, docs, hashes).

### Explicit non-goals

- Multi-tenant control plane, LSP, federation, AI authoring, hosted UI.
- Expanded streaming / CDC; DataFusion Gate B graduation.
- New orchestrator integrations beyond existing contracts.
- Removal of transitional SparkForge adapters (major only).
- Wire-schema major resets disguised as foundation work.
- Graduating `etlantic.quality/1` or dropping the Beta classifier.

## Workstream 1 — Removals

**Owner:** core API maintainer  
**Purpose:** clear the stable-foundation path of demoted aliases and the
`DataContractModel` provisional name.

| ID | Deliverable | Acceptance |
|---|---|---|
| `037-R01` | Remove remaining `_DEMOTED_ALIASES` | Importing removed root names fails closed; owning-module imports work |
| `037-R02` | Remove `DataContractModel` | Prefer `ContractModel` / `Data`; migration + tests |
| `037-R03` | Changelog + migration notes | [MIGRATION_0_36_TO_0_37](MIGRATION_0_36_TO_0_37.md) and CHANGELOG list every removal |
| `037-R04` | Update removal inventory targets | [REMOVAL_CANDIDATES_0_37](REMOVAL_CANDIDATES_0_37.md) Target columns say executed |

## Workstream 2 — Testing graduation

**Owner:** testing maintainer  
**Purpose:** graduate the 0.37 preview freeze into the stable
`etlantic.testing` foundation.

| ID | Deliverable | Acceptance |
|---|---|---|
| `037-T01` | Public case/result/snapshot contract | Documented stable; no private underscore imports required |
| `037-T02` | Cross-engine semantic cases | Advertised Polars / Pandas / SQL / PySpark intersection |
| `037-T03` | Fault / cancellation / unknown-effect fakes | No production system or resolved secret required |
| `037-T04` | Explicit snapshot update workflow | Reviewable, deterministic, redacted, size-bounded |
| `037-T05` | Isolated-wheel example | Clean directory; public imports only |
| `037-T06` | Independent application CI proof | Third-party or out-of-monorepo project uses public testing API |

## Workstream 3 — Acceptance suite 1–21

**Owner:** release + domain maintainers  
**Purpose:** executable evidence for every roadmap acceptance item.

| ID | Deliverable | Acceptance |
|---|---|---|
| `037-A01` … `037-A21` | One evidence row per acceptance item 1–21 | Pass, or explicit non-blocking disposition (DataFusion item 15 = experimental / no obligation) |
| `037-A-ARROW` | Item 14 Arrow boundary | Gate A only; diagnosed fallback; no Gate B claim |
| `037-A-DF` | Item 15 DataFusion | Recorded as experimental; does not block foundation |

Harness and corpus live under `tests/stable_foundation/` with
`scripts/check_stable_foundation.py` as the aggregated gate.

## Workstream 4 — Security matrix

**Owner:** security maintainer  
**Purpose:** map every mandatory Security Model control to automated
verification and residual risk.

| ID | Deliverable | Acceptance |
|---|---|---|
| `037-S01` | `SECURITY_VERIFICATION_MATRIX.md` | Control → owner → automated check → residual risk |
| `037-S02` | Redaction / trust / boundedness gates | Zero resolved secrets; production fail-closed; hostile fixtures |
| `037-S03` | Plugin allowlist / digest / protocol checks | Fail before untrusted import |
| `037-S04` | Schema-history / safe-I/O / outbound proofs | No source rows; roots and overwrites explicit |

## Workstream 5 — Stability freeze

**Owner:** core + Plugin SDK maintainers  
**Purpose:** freeze the foundation envelope without silent surface drift.

| ID | Deliverable | Acceptance |
|---|---|---|
| `037-F01` | Surface / schema / diagnostic inventories | Drift requires reviewed update |
| `037-F02` | Protocol statuses match locked dispositions | `scheduler/1` stable MVP; `quality/1` provisional; testing graduated |
| `037-F03` | Plugin floor `>=0.37,<0.38` | First-party packages and docs agree |
| `037-F04` | Beta classifier retained | Release checks still require Beta |

## Workstream 6 — Release rehearsal

**Owner:** release maintainer  
**Purpose:** prove the exact artifacts users install.

| ID | Deliverable | Acceptance |
|---|---|---|
| `037-D01` | `WHATS_NEW_0_37.md` / migration / exit gate / findings | Planning artifacts exist; evidence linked at close |
| `037-D02` | Build all first-party distributions | Versions align; hashes recorded |
| `037-D03` | Clean-env install + smoke | Core Quickstart without engine deps |
| `037-D04` | Immutable `/en/v0.37.0/` docs | HTTP 200 before announcement |
| `037-D05` | Tag/publish rehearsal | Digests, attestations, rollback notes |

## Delivery sequence

### Wave 0 — Lock planning artifacts

Land this plan, exit gate, findings ledger, What's New, and migration guide.
Update indexes, deprecation policy, and removal-candidate targets.

### Wave 1 — Removals and surface freeze prep

Complete `037-R01`–`037-R04` and inventory snapshots for `037-F01`–`037-F04`.

### Wave 2 — Testing graduation and acceptance corpus

Complete `037-T01`–`037-T06` and acceptance items 1–21 evidence under
`tests/stable_foundation/`.

### Wave 3 — Security matrix

Complete `037-S01`–`037-S04`.

### Wave 4 — Release rehearsal and exit gate

Complete `037-D01`–`037-D05`, resolve every P0, disposition every P1, then close
`EXIT_GATE_0_37.md`.

## Quantified exit scorecard

| Measure | Required value |
|---|---:|
| Acceptance suite items 1–21 with executable evidence (or explicit non-blocking disposition) | 100% |
| Demoted root aliases remaining on public root | 0 |
| `DataContractModel` still importable as public alias | 0 |
| Testing graduation gates met (public imports, isolated wheel, redaction) | 100% |
| Security matrix controls with owner + automated verification | 100% |
| Resolved secret values in retained artifacts | 0 |
| Production plugin paths that bypass allowlist/compatibility checks | 0 |
| Unresolved P0 findings | 0 |
| Remaining P1 findings without owner, phase, mitigation, and rationale | 0 |
| Unversioned wire-schema changes | 0 |
| Release-facing immutable documentation URLs returning non-200 | 0 |
| Runnable documentation claims without executed CI evidence | 0 |

## Finding severity and closure

| Severity | Meaning | Release treatment |
|---|---|---|
| P0 | Foundation corruption, security boundary failure, silent semantic fallback, unusable release artifact | Must close before 0.37 |
| P1 | Material adoption, migration, performance, documentation, or support risk | Close or formally defer with owner, mitigation, target phase, and non-blocking rationale |
| P2 | Localized usability or maintainability defect | May defer with owner and target |
| P3 | Cosmetic or opportunistic improvement | Backlog |

## Risk register

| Risk | Impact | Mitigation |
|---|---|---|
| Removals break quiet root imports | Adoption friction | Migration guide + fail-closed tests + owning-module examples |
| Testing “graduation” without isolated-wheel proof | False stability claim | Wheel-only gates and out-of-monorepo example |
| Acceptance item 15 treated as blocking | Scope creep / false Gate B claim | Explicit experimental disposition |
| Security matrix is documentation-only | Ungrounded readiness claim | Every control links an automated check |
| Beta classifier dropped accidentally | Messaging mismatch | `check_release` / docs gates retain Beta |

## Required companion documents

- `docs/11_DEVELOPMENT/FINDINGS_0_37.md`
- `docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md`
- `docs/11_DEVELOPMENT/EXIT_GATE_0_37.md`
- `docs/01_GETTING_STARTED/WHATS_NEW_0_37.md`
- `docs/11_DEVELOPMENT/REMOVAL_CANDIDATES_0_37.md`
- `docs/11_DEVELOPMENT/DEPRECATION_POLICY.md`
- `docs/11_DEVELOPMENT/SECURITY_VERIFICATION_MATRIX.md` (land during Wave 3)
- `CHANGELOG.md`
- `docs/release-facts.json`

## Progress reporting

Keep completion evidence in `EXIT_GATE_0_37.md`. Use:

| State | Meaning |
|---|---|
| Not started | No implementation evidence |
| In progress | Work exists but the acceptance condition is not met |
| Blocked | Named dependency prevents progress |
| Gate-ready | Implementation and focused tests pass |
| Closed | Exit-gate evidence is linked and reviewed |

## Review trigger

Review this plan whenever:

- a locked disposition would change;
- a new P0/P1 security or foundation finding appears;
- the acceptance suite scope changes;
- a first-party package changes maturity or classifier;
- a proposed feature would expand 0.37 beyond stable-foundation graduation.
