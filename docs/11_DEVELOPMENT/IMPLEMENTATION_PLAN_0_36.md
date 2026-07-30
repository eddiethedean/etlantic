---
status: plan
since: "0.35.0"
current_minor: "0.35"
audience: maintainer
---

# ETLantic 0.36 Implementation Plan — Joint Compatibility Burn-In

> **Status: Internal project plan.** ETLantic 0.35 is the current shipped
> minor; nothing in this document is available merely because it is planned
> here. The
> [main roadmap](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md)
> owns release order, [Capabilities](../01_GETTING_STARTED/CAPABILITIES.md)
> owns shipped behavior, and the eventual `EXIT_GATE_0_36.md` will own release
> evidence.

## Outcome

Release ETLantic and Medallantic 0.36 as one bounded compatibility-burn-in
milestone. The release must prove that supported users can upgrade, load and
regenerate durable artifacts, run representative pipelines across the
advertised engine intersection, and consume first-party plugins without a
silent semantic change, unplanned wire-schema reset, secret disclosure, or
unexplained Medallantic parity difference.

0.36 is an evidence and compatibility release. It is not a vehicle for broad
new product surface.

## Definition of done

The phase is complete only when all of the following are true:

1. The published 0.35 baseline is reproducible and any known release-integrity
   defect has a forward fix or an explicit compatibility fixture.
2. The `0.34 → 0.35` and `0.35 → 0.36` upgrade paths pass from isolated,
   published or locally built wheels.
3. Every supported public wire schema and protocol has a declared compatibility
   range and executable old/new reader-writer evidence.
4. Every first-party plugin passes its applicable public conformance suite from
   an isolated wheel installation.
5. Representative application-pipeline cases pass across the advertised local,
   Polars, Pandas, SQL, and PySpark capability intersection.
6. Medallantic semantic conformance and both legacy differential corpora pass
   with zero unexplained differences.
7. There are no unresolved P0 compatibility, security, parity, migration, or
   release-integrity findings.
8. Every remaining P1 has an owner, target phase, mitigation, and written reason
   it does not block the 0.38 stable foundation.
9. Documentation, migration guidance, release artifacts, and versioned Read the
   Docs pages are verified against the exact wheels users install.

## Authority and boundaries

When sources disagree, use this order:

1. Current-version capabilities, API, CLI, and package documentation define
   what ships.
2. The main roadmap defines milestone order and the 0.36 exit outcome.
3. This document defines the implementation sequence, evidence, and ownership
   for 0.36.
4. Domain plans define their own detailed semantics.
5. Tests, manifests, built wheels, release records, and the exit gate provide
   completion evidence.

The following boundaries are non-negotiable:

- ETLantic owns portable modeling, validation, deterministic planning, runtime
  coordination, evidence, and plugin contracts.
- Engine and orchestrator behavior remains in optional packages.
- Bronze, silver, and gold vocabulary remains in Medallantic; it must not enter
  ETLantic core.
- Plans, reports, diagnostics, snapshots, migration reports, and test evidence
  must never contain resolved secret values.
- Production profiles require an explicit `plugin_allowlist` and fail closed.
- Schema-history and compatibility fixtures store schemas, fingerprints, and
  bounded metadata—not source rows.
- Airflow remains a compile target supplied by `etlantic-airflow`; core must not
  acquire an Airflow dependency.
- Experimental DataFusion behavior cannot graduate by assertion. It must pass
  the same applicable conformance, differential, security, performance, and
  documentation gates as other engines.

## Scope

### In scope

- Published-wheel upgrade and rollback evidence for 0.34, 0.35, and 0.36.
- Durable artifact compatibility for pipeline definitions, plans, reports,
  profiles, capabilities, interchange descriptors, quality expressions,
  facade definitions, provenance, and migration IR.
- Stable diagnostic identity and normalized failure evidence.
- First-party plugin compatibility and isolated-wheel conformance.
- Application-pipeline testing burn-in across the supported engine
  intersection.
- Medallantic migration, semantic, and legacy differential evidence.
- Security, redaction, boundedness, determinism, and performance regression
  gates affected by compatibility work.
- Documentation, release automation, versioned docs, and an auditable 0.36 exit
  gate.

### Explicit non-goals

- A managed server, registry, control plane, or multi-tenant runtime.
- LSP, remote federation, AI-assisted authoring, or new hosted UI.
- Expanded streaming or CDC semantics.
- New orchestrator integrations beyond proving existing contracts.
- Removal of transitional SparkForge adapters; those remain until a documented
  major release.
- A new wire-schema generation unless an existing schema cannot safely express
  required semantics and the migration is approved before implementation.
- Broad API redesign disguised as compatibility work.

## Entry gate

0.36 work may begin in parallel, but the compatibility baseline is not locked
until these conditions are satisfied:

| ID | Entry condition | Required evidence |
|---|---|---|
| `036-E01` | The 0.35 release-facing README and docs resolve to a live immutable version | HTTP 200 checks for every release-facing RTD link |
| `036-E02` | The warning-clean report metadata fix is available in a published patch, or 0.35.0 is recorded as a known-defect fixture | Clean-wheel Quickstart transcript plus legacy-report fixture |
| `036-E03` | Published tags remain immutable | Release record showing forward-fix version; no moved tag |
| `036-E04` | The exact supported 0.34 and 0.35 package set is archived | Wheel filenames, hashes, package metadata, Python range |
| `036-E05` | Current schemas, protocols, diagnostics, public imports, and CLI commands are snapshotted | Reviewed machine-readable inventories |
| `036-E06` | Baseline CI is green from source and current wheels | Links to successful checks and package jobs |

If 0.35.1 is used as the forward-fix baseline, the plan must preserve a
0.35.0 fixture for the warning and metadata-key migration. A patch release does
not erase compatibility responsibility for already-published artifacts.

## Compatibility vocabulary

Every matrix cell must use one of these outcomes:

| Outcome | Meaning |
|---|---|
| `compatible` | The reader accepts the artifact and preserves documented semantics |
| `migrated` | A versioned migration transforms the artifact without silent data loss |
| `regenerate` | The format is intentionally ephemeral; the user receives a documented deterministic regeneration path |
| `upgrade-required` | The older reader rejects a newer artifact with a stable actionable diagnostic |
| `unsupported` | The combination is outside the declared range and fails closed |

“Pass” does not always mean an old reader accepts a new artifact. It means the
observed result matches the declared compatibility contract. Silent field loss,
implicit fallback, warning-only corruption, or a generic traceback is never a
passing outcome.

## Workstream 1 — Release baseline and inventory

**Owner:** release maintainer  
**Purpose:** ensure the burn-in measures real user artifacts rather than only
the current source tree.

| ID | Deliverable | Acceptance |
|---|---|---|
| `036-R01` | Close the 0.35 release-integrity follow-up | Versioned docs are live; the install pin contains the documented behavior |
| `036-R02` | Archive exact 0.34.x and 0.35.x wheel sets | Hash-verified manifest covers core, official plugins, facade, redirect, reference adapter, and experimental package |
| `036-R03` | Add a release-baseline manifest | Records version, Python range, schema/protocol inventory, package roles, hashes, and source tag |
| `036-R04` | Snapshot public imports, CLI, diagnostic codes, schemas, protocols, and plugin entry points | Drift requires an intentional reviewed update |
| `036-R05` | Establish the 0.36 finding ledger | Every P0/P1 has owner, state, evidence link, and disposition |

Proposed evidence:

```text
tests/fixtures/releases/
  v0_34/
    manifest.json
  v0_35/
    manifest.json
  v0_36/
    manifest.json
docs/11_DEVELOPMENT/FINDINGS_0_36.md
```

The repository should not commit third-party dependency caches. It may commit
manifests and project-owned golden artifacts; CI may retrieve project wheels
by exact version and verify their hashes.

## Workstream 2 — True reader-writer compatibility

**Owner:** core compatibility maintainer  
**Purpose:** replace current-reader-only burn-in with evidence from the actual
old and new packages.

### Artifact families

The matrix must cover:

- `etlantic.pipeline/1`
- `etlantic.plan/1`
- `etlantic.run_report/1`
- profile JSON
- `etlantic.capabilities/1`
- `etlantic.interchange/1`
- `etlantic.quality/1`
- facade definition/provenance extensions
- Medallantic migration IR
- versioned diagnostic and security-event payloads used across releases

### Required directions

For each supported family:

1. 0.34 writer → 0.35 reader
2. 0.35 writer → 0.34 reader
3. 0.35 writer → 0.36 reader
4. 0.36 writer → 0.35 reader
5. current reader → current writer round trip
6. unsupported schema/protocol → stable fail-closed diagnostic

Where 0.34 did not ship a family, record `unsupported` with evidence rather
than manufacturing a fixture.

### Deliverables

| ID | Deliverable | Acceptance |
|---|---|---|
| `036-C01` | Versioned fixture manifest for every artifact family | 100% of supported matrix cells have a fixture and expected outcome |
| `036-C02` | Isolated-wheel reader/writer harness | Writer and reader execute in separate environments using only public imports |
| `036-C03` | Semantic comparison layer | Compares identities, topology, policies, redacted metadata, and normalized outcomes—not only byte hashes |
| `036-C04` | Legacy run-report metadata migration | Known 0.35 bare keys load without warnings or semantic loss and rewrite to namespaced keys |
| `036-C05` | Unknown-field and unsupported-version tests | Readers fail with stable diagnostics; no silent dropping of security-relevant fields |
| `036-C06` | Deterministic rewrite evidence | Repeated migration/regeneration produces identical canonical output and fingerprint |
| `036-C07` | Diagnostic compatibility inventory | Existing codes retain meaning; intentional changes have aliases or migration notes |

The existing `check_pipeline_codec_burn_in.py` and
`check_codec_burn_in_matrix.py` remain useful current-reader gates, but they do
not satisfy `036-C02` by themselves.

## Workstream 3 — Protocol and public-surface decisions

**Owner:** core and Plugin SDK maintainers  
**Purpose:** leave no provisional protocol on the stable-foundation path.

| ID | Decision | Required outcome |
|---|---|---|
| `036-S01` | `etlantic.scheduler/1` | Promote to stable with conformance and recovery semantics, or move it explicitly off the stable-foundation path with migration guidance |
| `036-S02` | `etlantic.quality/1` | Promote, revise through a versioned migration, or retain as experimental outside the stable-foundation claim |
| `036-S03` | `etlantic.testing` preview | Freeze the minimum 0.36 case/result/snapshot contract needed for burn-in; final foundation graduation remains 0.38 |
| `036-S04` | `DataContractModel` compatibility alias | Confirm 0.38 removal disposition and ensure warnings/docs match the removal inventory |
| `036-S05` | Facade protocol and generated-definition provenance | Declare stable supported range across ETLantic and Medallantic |

Each decision requires:

- an architecture or protocol decision record;
- machine-readable surface-inventory update;
- conformance tests;
- migration guidance when behavior changes;
- explicit public documentation status;
- a `check_protocol_freeze.py` or equivalent automated gate.

No new public protocol should be introduced in 0.36 unless it is necessary to
close an already-promised stable-foundation abstraction.

## Workstream 4 — First-party package and plugin burn-in

**Owner:** package/plugin maintainers  
**Purpose:** prove independently installable artifacts, not monorepo imports.

### Package categories

| Category | Packages | Required proof |
|---|---|---|
| Core | `etlantic` | Public API, CLI, codec, runtime, docs transcript |
| Execution/compiler | Polars, Pandas, SQL, PySpark, Airflow, Prefect | Applicable discovery, capability, execution/compile, failure, and report conformance |
| Provider/bridge | Keyring, SQLModel | Applicable provider/bridge conformance, redaction, optional-dependency behavior |
| Facade | `medallantic` | Joint version, provenance, semantics, migration, differential evidence |
| Redirect | `etlantic-sparkforge` | Import/deprecation path and no unexpected behavior |
| Reference adapter | `etlantic-fastapi` | Installed-wheel import and documented bounded reference behavior |
| Experimental | `etlantic-datafusion` | Isolation plus existing experimental gates; no automatic graduation |

### Deliverables

| ID | Deliverable | Acceptance |
|---|---|---|
| `036-P01` | Build all thirteen distributions from the same candidate commit | Versions align; metadata and hashes recorded |
| `036-P02` | Install each distribution in a clean environment | No undeclared monorepo path, source checkout, or transitive optional dependency is required |
| `036-P03` | Run public conformance by package role | 100% of first-party plugins pass every applicable suite |
| `036-P04` | Test supported old/new core-plugin combinations | Declared ranges accept; unsupported ranges fail during compatibility checks before execution |
| `036-P05` | Verify production plugin trust | Missing allowlist, digest mismatch, and incompatible protocol fail closed before untrusted import |
| `036-P06` | Verify normalized failures | Missing backend, capability mismatch, timeout, cancellation, and write uncertainty produce stable evidence |
| `036-P07` | Verify optionality | Core wheel imports and driver-free Quickstart run without engine, database, Spark, Airflow, or Prefect dependencies |

## Workstream 5 — Application-pipeline testing burn-in

**Owner:** testing and engine maintainers  
**Purpose:** advance the 0.35 public preview toward the stable 0.38 testing
foundation.

### Canonical cases

Create a small, versioned case corpus using public `etlantic.testing` imports:

1. identity file pipeline;
2. typed projection and rename;
3. filter plus derived column;
4. join at the advertised portable intersection;
5. accepted/rejected quality outputs;
6. no-write validation intent;
7. append and replace intents;
8. deterministic plan/report snapshot;
9. deliberate contract mismatch;
10. capability rejection;
11. retryable failure followed by success;
12. cancellation/timeout terminal report;
13. unknown external-effect outcome;
14. secret reference and redaction proof.

Fixtures must be explicit, bounded, synthetic, and small. Snapshot artifacts
must not retain arbitrary source rows.

### Engine matrix

| Path | Required 0.36 evidence |
|---|---|
| Local Python | All applicable canonical cases |
| Polars | Portable capability intersection plus normalized failures |
| Pandas | Portable capability intersection plus normalized failures |
| SQL | SQLite evaluation set; PostgreSQL-only behavior separately capability-gated |
| PySpark | Local supported intersection with compatible JVM/Python matrix |
| Airflow | Deterministic compilation from a valid plan; no direct execution claim |
| Prefect | Bounded direct-execution scheduler cases if `scheduler/1` remains on the stable path |

### Deliverables

| ID | Deliverable | Acceptance |
|---|---|---|
| `036-T01` | Versioned application-case schema and fixtures | Public, deterministic, documented, and bounded |
| `036-T02` | Cross-engine semantic comparator | Ignores approved backend noise but detects row, contract, diagnostic, plan, and report differences |
| `036-T03` | Snapshot migration command or helper | Updates are explicit, reviewable, and deterministic |
| `036-T04` | Failure and recovery fakes | No production system, resolved secret, or unbounded data is required |
| `036-T05` | JUnit, JSON, and SARIF result proof | Machine output validates against documented schemas |
| `036-T06` | Installed-wheel example | Runs from a clean directory without repository-only imports |

0.36 does not claim final testing-foundation stability. It must record which
cases and helpers remain provisional for the 0.37 rehearsal and 0.38
graduation.

## Workstream 6 — Medallantic joint burn-in

**Owners:** Medallantic maintainer and core compatibility maintainer  
**Purpose:** prove the facade/core boundary and both legacy migration paths.

| ID | Deliverable | Acceptance |
|---|---|---|
| `036-M01` | 0.34 → 0.35 → 0.36 Medallantic definition fixtures | Definitions preserve medallion semantics and provenance |
| `036-M02` | Migration-IR old/new reader-writer matrix | Supported cells pass declared outcomes; unsupported cells fail with `MDL*` diagnostics |
| `036-M03` | SparkForge builder differential corpus | Zero unexplained semantic differences |
| `036-M04` | SQL builder/Moltres differential corpus | Zero unexplained semantic differences |
| `036-M05` | Native Medallantic cross-engine cases | Local, Polars, Pandas, SQL, and PySpark pass their advertised intersections |
| `036-M06` | Manual-migration diagnostic stability | `MDL200`–`MDL230` identities and remediation remain stable or have documented migration |
| `036-M07` | Adapter retention proof | Transitional imports still work with documented deprecation; no removal in 0.36 |
| `036-M08` | Boundary audit | No medallion layer types, names, or defaults enter ETLantic core |

Migration analysis must remain static and bounded: no importing untrusted user
code, resolving secrets, reading source rows, or mutating target projects.

## Workstream 7 — Security, resilience, and performance

**Owner:** security and runtime maintainers  
**Purpose:** ensure compatibility mechanisms do not weaken existing controls.

### Required adversarial cases

- secret-like keys in every extension bag;
- malformed, oversized, deeply nested, and cyclic-equivalent documents;
- fingerprint mismatch and tampered manifests;
- path traversal and unsafe URI schemes;
- incompatible or unallowlisted plugin metadata;
- unknown schema/protocol versions;
- malicious migration metadata;
- cancellation during write;
- retry after uncertain external effect;
- cross-profile artifact/cache reuse attempt;
- schema observation containing attempted source rows.

### Gates

| ID | Gate | Acceptance |
|---|---|---|
| `036-A01` | Redaction | Zero resolved secrets in plans, reports, diagnostics, logs, snapshots, fixtures, and CI artifacts |
| `036-A02` | Trust | Production plugin discovery and compatibility fail closed before untrusted import |
| `036-A03` | Bounded parsing | Size/depth/count limits have tests and actionable diagnostics |
| `036-A04` | Mutation safety | Schema/migration analysis is read-only unless an explicit reviewed command authorizes mutation |
| `036-A05` | Isolation | Artifact/cache identities preserve profile, security-domain, engine, and contract boundaries |
| `036-A06` | Terminal semantics | Cancellation, timeout, failure, and unknown-effect states remain normalized and durable |
| `036-A07` | Performance | Codec, planning, case-runner, and conformance overhead stay inside committed budgets |
| `036-A08` | Dependency audit | No new mandatory heavy or vendor-specific dependency enters core |

Any security regression is P0. Performance regressions above the approved
budget are P1 unless they create denial-of-service or unbounded-resource risk,
in which case they are P0.

## Workstream 8 — CI and evidence architecture

**Owner:** CI/release maintainer

### Required jobs

| Job | Purpose | Minimum matrix |
|---|---|---|
| `compatibility-current-reader` | Existing golden fixtures under current code | Ubuntu / Python 3.11 |
| `compatibility-isolated-wheels` | True old/new reader-writer subprocess matrix | Ubuntu / Python 3.11–3.13 |
| `plugin-wheel-conformance` | Each first-party package from built wheels | One job per package role; supported Python floor and ceiling |
| `application-cases` | Cross-engine semantic cases | Local, Polars, Pandas, SQL, PySpark |
| `medallantic-burn-in` | Definition, migration, semantic, and differential corpora | Source plus isolated core/facade wheels |
| `security-compatibility` | Hostile fixtures, redaction, trust, boundedness | Ubuntu / Python 3.11 |
| `release-rehearsal` | Build, install, smoke, docs, manifests, hashes | All thirteen candidate distributions |

OS-specific plugin claims must run on their supported operating systems.
Core lint/test remains on Linux, macOS, and Windows for Python 3.11–3.13.

### Evidence rules

- A required job cannot be marked passing by a registry string alone; CI must
  execute the named command.
- Every matrix result emits a machine-readable summary.
- Skips require a declared reason and cannot silently satisfy a required cell.
- Flaky retry may expose infrastructure instability, but a passed retry must
  retain the failed attempt as evidence.
- Golden updates require an explicit maintainer command and reviewed manifest
  diff.
- CI artifacts must be secret-free and size-bounded.

Proposed summary schema:

```json
{
  "schema": "etlantic.compatibility_evidence/1",
  "release": "0.36.0",
  "matrix": "old-new-readers-writers",
  "passed": 0,
  "failed": 0,
  "skipped": 0,
  "findings": []
}
```

The exact schema remains internal unless a separate public-use case is
approved.

## Workstream 9 — Documentation and release

**Owners:** documentation and release maintainers

| ID | Deliverable | Acceptance |
|---|---|---|
| `036-D01` | `WHATS_NEW_0_36.md` | Describes shipped outcomes, not implementation inventory |
| `036-D02` | `MIGRATION_0_35_TO_0_36.md` | Covers imports, metadata keys, protocols, artifacts, plugins, diagnostics, and regeneration paths |
| `036-D03` | `EXIT_GATE_0_36.md` | Links every quantified criterion to durable evidence |
| `036-D04` | Compatibility and surface inventories | Exact versions, statuses, ranges, and package roles match code |
| `036-D05` | Installed-wheel upgrade tutorial | Copy-pasteable 0.35 → 0.36 path with expected output and rollback |
| `036-D06` | Plugin maintainer upgrade guide | Shows compatibility declaration, conformance, and failure behavior |
| `036-D07` | Medallantic migration update | Covers both legacy builders and native definitions |
| `036-D08` | Release-facing links | Immutable `/en/v0.36.0/` pages return 200 before announcement |
| `036-D09` | Runnable example ledger | Every runnable claim maps to a companion that actually executes in CI |
| `036-D10` | External-link health gate | Network health is checked separately from internal anchor validation |

Before tagging, update `docs/release-facts.json`, package pins, support line,
roadmap summaries, capabilities, known limitations, API status, release notes,
and Read the Docs version instructions as one release transaction.

## Delivery sequence

The sequence is dependency-based, not a date commitment.

### Wave 0 — Repair and lock the baseline

Complete `036-E01`–`036-E06` and `036-R01`–`036-R05`.

Exit: maintainers can reproduce the precise 0.34/0.35 state—including known
defects—from isolated wheels and immutable documentation.

### Wave 1 — Build the compatibility harness

Complete `036-C01`–`036-C07`, then land the machine-readable result summary.

Exit: the repository proves actual old/new reader-writer outcomes rather than
only current-reader round trips.

### Wave 2 — Decide protocols and burn in packages

Complete `036-S01`–`036-S05` and `036-P01`–`036-P07`.

Exit: every official package has a declared range and isolated-wheel evidence;
no unresolved provisional protocol remains on the stable-foundation path.

### Wave 3 — Burn in user pipelines and Medallantic

Complete `036-T01`–`036-T06` and `036-M01`–`036-M08`.

Exit: representative public user workflows and both Medallantic migration
paths pass across their advertised engine intersections.

### Wave 4 — Adversarial, performance, and release rehearsal

Complete `036-A01`–`036-A08`, all required CI jobs, and `036-D01`–`036-D10`.

Exit: the exact candidate wheels, docs, hashes, compatibility evidence,
migration guide, and rollback procedure have been rehearsed.

### Wave 5 — Close the exit gate

1. Freeze the candidate commit.
2. Run the full source and isolated-wheel matrices.
3. Resolve every P0.
4. Review and disposition every P1.
5. Build all thirteen distributions.
6. Verify SHA-256 digests, package metadata, and attestations.
7. Install core and every official package in clean environments.
8. Build and activate `/en/v0.36.0/`.
9. Publish `EXIT_GATE_0_36.md` with immutable evidence links.
10. Tag and publish only after all prior steps pass.

## Quantified exit scorecard

| Measure | Required value |
|---|---:|
| Supported wire-schema/protocol matrix cells with executable evidence | 100% |
| First-party plugins passing applicable public conformance from wheels | 100% |
| Required application-case/engine cells passing | 100% |
| Unexplained Medallantic semantic differences | 0 |
| Unversioned wire-schema changes | 0 |
| Resolved secret values in retained artifacts | 0 |
| Production plugin paths that bypass allowlist/compatibility checks | 0 |
| Unresolved P0 findings | 0 |
| Remaining P1 findings without owner, phase, mitigation, and rationale | 0 |
| Release-facing immutable documentation URLs returning non-200 | 0 |
| Runnable documentation claims without executed CI evidence | 0 |

## Finding severity and closure

| Severity | Meaning | Release treatment |
|---|---|---|
| P0 | Compatibility corruption, security boundary failure, silent semantic fallback, unexplained parity failure, unusable release artifact | Must close before 0.36 |
| P1 | Material adoption, migration, performance, documentation, or support risk | Close or formally defer with owner, mitigation, target phase, and non-blocking rationale |
| P2 | Localized usability or maintainability defect | May defer with owner and target |
| P3 | Cosmetic or opportunistic improvement | Backlog |

A finding is closed only when its regression test and durable evidence land.
Changing severity without written rationale does not close it.

## Risk register

| Risk | Impact | Mitigation |
|---|---|---|
| Current burn-in is mistaken for true old-reader testing | False compatibility confidence | Separate released writers/readers into isolated environments |
| 0.35 published defects are hidden by current source fixes | Users reproduce warnings or incompatible metadata | Preserve 0.35.0 fixtures and publish a forward fix |
| Additive `/1` changes are silently dropped by older readers | Security or semantic loss | Unknown-field tests plus explicit `upgrade-required` outcomes |
| Plugin suites pass only from monorepo paths | Published wheels fail | Wheel-only conformance jobs |
| Cross-engine comparisons over-normalize real differences | Semantic regressions escape | Document every normalization and retain engine-native evidence |
| PySpark/SQL infrastructure causes flaky gates | Release stalls or false passes | Separate infrastructure errors from semantic outcomes; retain retries |
| Medallantic policy leaks into core | Core boundary erosion | Boundary audit and import/type inventory |
| Snapshot fixtures retain sensitive or unbounded rows | Security and repository growth | Synthetic bounded fixtures, redaction, size gates |
| Protocol freeze is rushed to meet the milestone | Long-term compatibility burden | Decision record, external-plugin review, and migration rehearsal |
| Docs describe `main` while pins install older wheels | Adoption failure | Execute tutorials against exact release wheels and immutable docs |

## Open decisions

These decisions must close before Wave 2 exits:

1. Is `etlantic.scheduler/1` stable enough for the foundation path, or should it
   be explicitly rescheduled?
2. Does `etlantic.quality/1` graduate, migrate, or remain experimental outside
   the stable-foundation claim?
3. Which `etlantic.testing` types are stable in 0.36 and which remain preview?
4. What is the supported patch baseline for the 0.35 → 0.36 upgrade:
   0.35.0, newest 0.35.x, or both? The matrix should normally retain both.
5. Which SQL behaviors belong to the portable intersection versus
   PostgreSQL-only capability rows?
6. Which PySpark/JVM combinations are release-blocking?
7. Are any DataFusion gates mature enough to propose graduation? Default: no.

Record each answer in the relevant architecture/protocol decision and link it
from the 0.36 finding ledger.

## Initial ordered backlog

This is the recommended implementation order:

1. Publish or document the 0.35 forward-fix baseline and activate immutable
   versioned docs.
2. Add 0.34/0.35 release manifests and hash verification.
3. Capture the public surface, protocol, schema, diagnostic, CLI, and plugin
   inventories.
4. Add the 0.36 finding ledger and severity policy.
5. Design the isolated-wheel reader/writer harness.
6. Expand artifact fixtures through 0.35, including known-defect fixtures.
7. Add semantic comparators and declared compatibility outcomes.
8. Implement legacy run-report metadata normalization.
9. Add unsupported-version and hostile-fixture coverage.
10. Decide `scheduler/1` and `quality/1`.
11. Freeze the minimum 0.36 `etlantic.testing` contract.
12. Build all-package wheel conformance jobs.
13. Add old/new core-plugin range tests.
14. Create the canonical application-pipeline case corpus.
15. Run the corpus across local, Polars, Pandas, SQL, and PySpark.
16. Add Airflow compilation and Prefect scheduler-specific cases.
17. Expand Medallantic definition, migration-IR, and differential fixtures.
18. Add security, boundedness, redaction, failure, and performance gates.
19. Write migration, upgrade, plugin-maintainer, and release documentation.
20. Rehearse the exact candidate wheels and close `EXIT_GATE_0_36.md`.

## Progress reporting

Update this plan when a workstream changes status, but keep completion evidence
in `EXIT_GATE_0_36.md`. Use:

| State | Meaning |
|---|---|
| Not started | No implementation evidence |
| In progress | Work exists but the acceptance condition is not met |
| Blocked | Named dependency prevents progress |
| Gate-ready | Implementation and focused tests pass |
| Closed | Exit-gate evidence is linked and reviewed |

The phase must not be declared complete because code exists, because source
tests pass, or because a tag was created. Completion requires the quantified
scorecard against the exact released artifacts.

## Required companion documents

Create or update these as implementation proceeds:

- `docs/11_DEVELOPMENT/FINDINGS_0_36.md`
- `docs/11_DEVELOPMENT/MIGRATION_0_35_TO_0_36.md`
- `docs/11_DEVELOPMENT/EXIT_GATE_0_36.md`
- `docs/01_GETTING_STARTED/WHATS_NEW_0_36.md`
- `docs/10_REFERENCE/SURFACE_INVENTORY.md`
- `docs/10_REFERENCE/WIRE_SCHEMA_RANGES.md`
- `docs/10_REFERENCE/COMPATIBILITY.md`
- `docs/07_PLUGIN_SDK/PROTOCOL_EVOLUTION.md`
- `packages/medallantic/ROADMAP.md`
- `packages/medallantic/docs/sparkforge-migration.md`
- `CHANGELOG.md`
- `docs/release-facts.json`

## Review trigger

Review this plan whenever:

- a public schema or protocol status changes;
- a new P0/P1 compatibility or security finding appears;
- the supported Python/backend matrix changes;
- a 0.35 patch changes the upgrade baseline;
- a first-party plugin changes package role or maturity;
- the 0.37 release-candidate scope changes;
- a proposed feature would expand 0.36 beyond compatibility burn-in.
