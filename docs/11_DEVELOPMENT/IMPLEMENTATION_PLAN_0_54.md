---
title: ETLantic 0.54 Implementation Plan
description: Bounded implementation contract for adaptive conformance, scan pushdown, fusion, and qualification.
plan_status: current
plan_last_reviewed: 0.53.0
---

# ETLantic 0.54 Implementation Plan

Adaptive Conformance, Qualification, and Graduation

This contract owns increment I3 and Phase 10 of the
[adaptive program](IMPLEMENTATION_PLAN_0_51.md). It defines work for Luna;
it is neither implementation, passing evidence, nor release approval.
**REQUIRED BEHAVIOR** is normative. **RECOMMENDED IMPLEMENTATION** permits
internal adaptation while preserving the public contract and acceptance criteria.

The scope owner explicitly chose to include the missing reference-topology
pushdown/fusion implementation in 0.54. That decision resolves the conflict
between the unfused 0.53 launch rows and the frozen program reference fixture.
The extension below is limited to one Polars source/filter/projection signature;
general fusion and general connector pushdown remain outside this change.

The implemented candidate requires explicit placement bindings for all five
nodes of the reference. This conservative boundary makes the proven fusion
credits assignment-independent within the existing additive objective; partially
bound candidates receive no hypothetical fusion credit or lowering.

### Implementation Completion Boundary

The scope owner subsequently removed external completion gates. Completion of
the initial implementation requires implemented behavior, local tests and quality
gates, truthful local evidence, documentation and the implementation report.
It does not require remote CI runs, third-party action, a named release owner,
independent approval or a graduation decision. These remain optional follow-up
work for release/graduation, not blockers to this implementation handoff.
Implement and locally test the evidence-verification and approval safeguards;
keep actual remote observations absent and graduation pending unless obtained.
Never invent external evidence or promote Experimental rows to Available to
satisfy completion. This boundary takes precedence over external proof language
elsewhere in the historical program plan and exit gate for this session.

## Architecture Summary

Reuse the existing planner, solver, codecs, whole-DAG admission, LocalScheduler,
physical host, portable compilers and Arrow Gate A. Add a narrowly eligible native
scan composition and an independent qualification layer:

```text
static logical scope + trusted descriptors
  -> existing target candidates and deterministic placement
  -> connected regions; exact source/filter/project fusion when proven
  -> fingerprinted physical DAG and stored portable members
  -> whole-DAG admission with source/compiler/contract/binding pins
  -> bounded source snapshot + one composed Polars lazy query
  -> one Arrow transfer -> real Pandas transform -> validation -> publication
  -> sanitized per-environment observations
  -> independent exact-row graduation decision
```

The reverse Pandas→Polars handoff is independently qualified using the existing
unfused path. It receives no implicit Pandas source-pushdown or fusion claim.
Conformance observes behavior; reviewed packaged release data establishes
availability. The stored physical DAG is scheduling authority, and publication
is the only commit authority.

## Repository Ground Truth

Baseline: commit `ecf515f317fc5439c39206df0b79194f0f56fab6`, branch `main`,
package **0.53.0**, inspected **2026-09-16**. The worktree was clean before this
planning-only edit; fast-forward pull reported already up to date.

| Inspected surface | Actual behavior | Consequence |
|---|---|---|
| Authorities/backlog | ROADMAP 0.51–0.54, accepted ADR-025, program freeze/plan/gate, 0.52/0.53 plans/gates; live epic #30, stories #39/#40, tasks #78–#87/#94/#95 | Preserve staged contracts and frozen limits; open issue status alone does not establish absent code |
| Adaptive planner | `planning/adaptive.py`, `adaptive_budget.py`, `plan/planner.py` implement inventory, candidates, exact solver, regions and lowering | Extend existing analysis/lowering; no second solver |
| Fusion/pushdown | Regions set `fused=False`; compute units are singletons; objective credit can reference claims, but does not execute them | Region membership, fusibility and content-reference syntax are not proof of actual fusion or pushdown |
| Wire/public API | `plan/adaptive_model.py`, `physical.py`, schemas/codecs, public plan/runtime exports; generated checks currently recognize 0.52/0.53 | Extend generated 0.54 validation without disabling historical checks or introducing a planner-label bypass |
| Execution | `LocalScheduler` performs admission and builds the host view; `PhysicalScheduler` delegates; physical loop is in `LocalOrchestrator` | Add composed execution in this physical branch; ordinary sequential node execution is not fused execution |
| Dataframe/compilers | Polars compiler produces native lazy actions; Polars lazy validation inspects schema; ordinary compiler reports describe host pushdown as not applicable | Positive scan pushdown belongs to the exact new scan/fusion context, not every Polars compiler invocation |
| Storage/connectors | Public `StorageBinding.read/write` return process-local values; `PipelineRuntime.register_storage` exists; physical host deliberately excludes source-connector path | Use a bounded optional storage adapter; do not redesign connector sessions or enable all connectors |
| Support gate | `adaptive_support.py/.json`: Experimental, 13 exact rows, 50 observation IDs, pinned backend versions; multi-member compute rejected | Preserve existing row boundaries and add exactly one independent fused signature |
| Testing/evidence | Public physical/interchange smoke and compiler/connector suites exist; no adaptive provider suite; 0.52 planning artifacts and 0.53 sanitized execution aggregate exist | Publish conformance and fresh observations; planning e2e artifacts cannot qualify runtime |
| Dependencies/packages | Python >=3.11; supported CI 3.11/3.12/3.13; uv workspace with 23 optional packages, engine-free core | Keep Polars/Parquet execution in the optional Polars package; no new core engine dependency |
| Persistence | Local workspace/checkpoint/report stores and atomic JSON/CSV publication; CP/durable/remote /2 excluded | No database migration, durable queue or control-plane expansion |
| CI | `checks.yml`: Linux/macOS/Windows × three Python minors, exact adaptive backends and separate environment artifacts; existing lint/type/security/compatibility/docs/build gates | Add observed completeness aggregation, not just a declared platform matrix |
| Docs/examples | Public runtime/API docs and 0.53 gate describe Experimental execution; Planning Hub/current capability rows contain stale statuses | Update statements needed for truthful 0.54 behavior; avoid global editorial cleanup |

Relevant tests inspected include 0.51 wire/Profile, 0.52 planner/remediation,
0.53 execution/physical qualification/protected reviews, definitions and fallback.
Local baseline observations: doctor passed; focused adaptive tests **62 passed**
with 10 existing logical metadata namespace warnings; docs checks passed.
Default 0.53 evidence verification rejected the committed-evidence comparison.
Its source digest matches, but local Darwin/arm64/Python 3.11.15 differs from
declared Linux/aarch64/Python 3.11.16. The script emits no retained fresh record
on that rejection, so this is not full-campaign or nine-cell qualification proof.

GitHub issues were read through authenticated access. In particular,
[#147](https://github.com/eddiethedean/etlantic/issues/147) documents inaccurate
observation provenance in the retained 0.53 snapshot despite independent CI
proof; matching its source digest does not repair that provenance.

## Change Boundary

### Problem and Desired Outcome

Experimental local execution lacks a complete independent qualification and
public participation contract. The frozen
[#80 reference](https://github.com/eddiethedean/etlantic/issues/80) additionally
requires actual predicate/projection pushdown and fusion absent from the launch
rows. After this change, the exact reference topology executes through a proven
scan composition, providers can test their claims with public APIs, and
operators can reproduce a dated, truthful support matrix and rollback procedure.

### In Scope

- Existing 13 unfused rows, their exact applicable operation/contract/I/O/policy
  signatures, and independent Local/Polars/Pandas/bidirectional qualification.
- One new local Polars-Parquet→Pandas reference row with source/filter/projection
  fused into a single physical compute unit, scan predicate/projection pushdown,
  one Arrow handoff, Pandas transformation, validation and publication.
- Safe optional source adapter, portable composition capability, stored
  descriptors, exact eligibility, admission pins, fused lifecycle/attribution.
- Public provider conformance, graph/order, differential/failure, security,
  compatibility/consumer/resource and nine-environment evidence campaigns.
- Fresh local evidence/provenance, pending maturity decision support, scoped findings,
  author/provider/operator/reference/migration docs and runnable examples.
- Necessary bounded remediation of supported behavior exposed by the campaign.
  A new engine/shape/optimization requires a contract amendment.
- Lockstep 0.54 release preparation after qualification; tag/publish remains
  separate from implementation and cannot be inferred from this plan.

### Touched Surface

| Area | Expected files |
|---|---|
| Native optional source/composition | New `packages/etlantic-polars/src/etlantic_polars/parquet_storage.py`; compiler and public factories/manifest |
| Static fusion descriptors | New `src/etlantic/transform/fusion.py`; public exports; `planning/adaptive.py` and budget owners |
| Wire/integrity | Plan physical/adaptive models, codecs and schemas where required; generated identity and coverage checks |
| Runtime | Admission/support/bundle, physical host, orchestrator, dataframe/native execution helpers; narrowly scoped extraction permitted |
| Conformance/campaigns | New `testing/adaptive.py` and exports/fixtures; tests alongside plan/runtime/compatibility owners and new adaptive conformance area |
| Evidence/CI | New `scripts/check_adaptive_0_54.py`, phase AC/case ledger, evidence directory, checks aggregation and relevant release/docs gates |
| Docs/release | Phase exit/findings/migration/release docs, adaptive guides/examples/API/CLI/navigation; synchronized workspace metadata/manifests/lock at release preparation |

No connector-session redesign, new database tables, general orchestrator rewrite
or replacement planner is required.

## Public Contract — REQUIRED BEHAVIOR

### Strategy, Scope and Compatibility

Explicit remains the default; fallback remains `error`. Existing class and
PipelineDefinition request capture/precedence, eligible targets, selection,
portable-only eligibility and independently built /1 fallback remain required.
Stored /2 never downgrades. Ordinary /1 canonical bytes/fingerprints gain no
adaptive data. Valid historical /2 remains readable; old readers and unqualified
consumers reject before effects. Current package/evidence pin drift can make an
old executable plan require replanning without making its historical reader fail.

No new Profile optimization switch is added. The new fusion applies only after
ordinary node placement when its full static eligibility and registered
source/compiler evidence match. The selected topology is stored, not chosen at
runtime. A live boundary invalidates admission; it cannot silently split a stored
fused unit or substitute a provider.

### Bounded Parquet Source

Publish `etlantic_polars.create_parquet_storage()` returning a read-only
`PolarsParquetStorage` implementing the existing public StorageBinding.
Register explicitly with `runtime.register_storage("polars-parquet", storage)`.
A BindingDescriptor captures provider/version/format, logical relative location,
configuration, contract and static capability evidence through existing
registries. No automatic trust of a manually installed/registered object.

Binding configuration is closed and versioned:
`schema="etlantic.polars_parquet_source/1"`, `max_bytes`, `max_rows`.
Defaults are 64 MiB and 100,000 rows; maxima are 256 MiB and 1,000,000 rows.
Bounds are positive non-boolean integers; excess configuration rejects during
validation/planning. Only a single relative local Parquet file under SafeIoPolicy
is supported. Reject URLs, cloud locations, globs, directories, credentials,
symlink escape, hive partitioning, multiple files and custom read options.
write raises a safe unsupported-operation error before touching a destination.

Planning reads static descriptors only: no file open/list/schema/footer/hash,
compiler execution or secret resolution. Admission verifies captured policy,
type/factory identity, adapter configuration/version/evidence and binding before
any resource or file I/O, pins the source object, and passes frozen descriptors
to execution. File existence/schema/row count are checked after admission.
Missing/corrupt/wrong-schema input fails as source read/validation, not as a
pretended planning observation.

After admission, resolve the file under SafeIoPolicy and copy it through a
verified source handle into owned, bounded immutable bytes. No filesystem
snapshot, artifact root or additional policy approval is needed. Renaming or
replacing the source or its parent cannot change the native scan's input.
Enforce byte limit while copying. Before constructing any Arrow or Polars
reader, parse bounded Compact-Thrift footer framing and remove optional file
key/value metadata, including ARROW:schema; never invoke source-supplied Arrow
extension deserializers. Enforce the footer row limit before native inspection.
Require at most eight primitive columns and enforce the same
byte ceiling on total declared uncompressed Parquet column-chunk sizes, with
actual decode failures handled safely. Reject variable-width and nested source
types, even in projected-away columns; compressed file size alone is not a
decoded memory bound. Scan the sanitized immutable buffer; a snapshot failure
blocks downstream work. Retain it until native query work drains, then release
the buffer. There are no disk snapshot cleanup obligations; compatibility
cleanup inspection returns no tokens and unknown reconciliation tokens reject.
Memory includes bounded copies during sanitization and native construction.
PyArrow >=14 remains supported without newer extension-control keywords.
Source bytes
may be copied in full; this contract makes no byte-I/O performance claim.

Public ordinary read uses an eager bounded result so an independent explicit
baseline can execute the same source. A process-local `open_scan` method on the
exact optional adapter exposes the bounded snapshot-backed LazyFrame to the
fused host. Native frame/path/snapshot handles never enter wire records.
Existing connector /1 protocols and existing storage APIs do not change.

### Frozen Reference Signature and Portable Composition

New support signature:
`scan-filter-project-chain/1:polars-pandas`. The graph is exactly:

```text
raw[polars-parquet, Polars]
  -> filter[Polars]
  -> project[Polars]
  -> consumer[Pandas]
  -> out[memory|json|csv|null]
```

raw/filter/project each have one output; transformation members have one input.
Only the project output escapes the fused group; no intermediate observer,
fan-out, checkpoint/reuse/collection, effect/security/selection boundary,
row-changing validation or publication inside it. A validation physical barrier
follows consumer; sink compute prepares and the separate publication commits.
Exactly one directional Arrow Gate A transfer separates project and consumer.

The source and intermediate contracts are schema-provable nullable primitive
columns: signed int64 and boolean, required column names, no
aliases/default factories/coercion rules/field constraints/custom validators,
computed fields, nested values or extra-field rejection. Source schema checks
validate all required columns, including columns dropped by projection, before
native filtering. Nullable types avoid silently discarding a null violation.
Unsupported contracts remain ineligible for fusion; they are not weakened.

filter is one portable filter with a column-to-bound-parameter equality predicate;
its column is signed int64, its parameter is a non-null signed int64 and null
comparison uses the frozen portable semantics. project is a non-empty ordered
selection of existing columns without expressions or renaming. Include an unused
source column so projection proof is meaningful. Consumer is a separately
compiled portable select on Pandas. No UDFs, SQL, string predicates, casts,
arithmetic, aggregations, joins, sorting or dynamic parameters beyond the captured
scalar are permitted in this new fused signature.

Add public immutable FusionMember and FusionDescriptor in `etlantic.transform`.
FusionMember represents each of the two transformation members and binds its
logical node, original portable IR fingerprint/definition, input/output port,
contract fingerprints and wiring. The source has its own source/binding record,
not a fabricated portable IR definition. FusionDescriptor binds
schema `etlantic.portable_fusion/1`, ordered logical nodes (including the
source), target/compiler/source identities, member/edge/contract/policy digests,
input snapshot strategy, boundary output and immutable proof references.
Definitions remain their original stored portable members; a descriptor does
not store native query strings, frames or executable objects.

Define an additive optional PortableFusionCompiler protocol:
`analyze_fusion(descriptor, *, context: TransformPlanningContext)` returns a
TransformSupportReport; `compile_fusion(descriptor, *,
context: TransformCompileContext)` returns existing CompiledTransform.
Its implementation composes the two original IR definitions with deterministic
alpha-renaming of action/input/output/lineage identities. Existing compiler
execute accepts that artifact plus the admitted lazy input; no normal compiler
API or ordinary host_pushdown finding is globally changed.

Static analysis proves the exact operation/wiring/type regime against validated
source/compiler evidence. Pushdown findings name canonical predicate/projection
capabilities with exact source-boundary and member attribution. Missing/unknown
proof cannot earn positive objective credit. Keep the frozen solver tuple;
populate its positive facts only when this exact composition is proven.
Different execution signatures cannot borrow each other's proof.

Native implementation uses the existing Polars portable lowering. Polars
documents predicate and projection placement at the scan level in its
[lazy optimization contract](https://docs.pola.rs/user-guide/lazy/optimizations/).
This describes the design mechanism; qualification must establish behavior on
the pinned installed version independently.

### Physical Model, Admission and Fused Execution

Use existing /2 plan and physical-unit /1 containers with fingerprinted
namespaced descriptors; add schemas for new nested records. Keep closed field
validation. Generated 0.54 plans participate in the same strict identity,
policy, logical coverage and dependency validation as 0.52/0.53.

Map raw/filter/project to exactly one compute unit whose logical_nodes are that
canonical ordered tuple. Internally owned logical edges need a validated member
route within this descriptor, not a physical self-dependency. External edges
retain complete acyclic physical paths. Region membership stays maximal and
connected; a fused subgroup is recorded explicitly rather than marking unrelated
members of a larger region fused. Unit metadata and fusion records distinguish
region compatibility from physical realization; update region identity checks
accordingly without relabeling historical regions.

Admission validates every member/contract/IR/source/compiler/proof/port/policy
and all later units before acquisition or reads. Source snapshot/type/schema
checks occur in the admitted fused compute invocation. Preserve per-node stored
implementation records and add the fusion record at the unit boundary; existing
source `read` and sink `prepare` roles remain identifiable.

A dedicated fused host operation creates the lazy scan, composes/compiles once,
validates each schema boundary and executes the resulting lazy query once to
produce the boundary frame. Do not invoke _execute_node once per logical member,
materialize every intermediate, or call an engine-name fallback. Runtime may
build/inspect native plans only after admission. Query explain output is
provider-controlled and can contain paths/parameters: inspect it in process and
emit only sanitized booleans/IDs/digests, not raw text.

Prove predicate placement inside the native scan and that scan projection includes
only output plus predicate-required columns. Instrument real native execution
and compiler dispatch; metadata flags and a matching output alone are insufficient.
Fusion proof includes one main composed collection and no intermediate eager
frame registration. Optional bounded metadata/count audits may add native
reductions; they are not extra logical compute dispatch or a performance claim.

Use the existing worker/native-execution/drain mechanism. Effective fused deadline
is the earlier of run deadline and the minimum member step budget measured from
unit start; this can fail earlier safely, never later. New fused signature permits
one attempt, standard/validate intents, fail validation outcomes and existing
no-write/overwrite semantics only. Retry>1, non-default step middleware/callbacks
requiring per-member artifacts, unsupported schema/quality checks or intermediate
selection make this fused signature ineligible before effects. Existing unfused
rows retain their independently proven retry behavior.

Emit logical lifecycle identities and terminal reports for all three members.
Successful schema checks/query establish the corresponding logical successes;
a schema/member compilation fault fails its attributable member and skips
dependants; a source/native scan fault fails raw and skips other members.
Unattributable query failure cannot manufacture member successes. Cancellation/
deadline marks active members terminal and blocks later publication.
Record fused physical attempt identity with each logical member, required
validation results and count invariants. A count may be explicitly unavailable
where the explicit API permits it; never substitute zero or fabricate statistics.
Do not publish intermediate row data just to populate reports.

All native result registration is deadline-fenced and attempt-private until
success. Snapshot/frame owners survive native cancellation until drain; unresolved
owners remain PMADP523. Arrow transfer and later publication keep existing
PMADP524 receipt/reconciliation semantics.

### Exact Qualification Matrix and Maturity

Preserve the 13 existing unfused rows: chain on Local/Polars/Pandas and both
directions (5), diamond and fanout single-target on each engine (6), directional
dual-port chain (2). Add only the one fused reference row above: **14 proposed
rows total**, before evidence-driven narrowing. Qualify lengths/selections and
operation/contract/policy signatures the recognizers actually accept, or narrow
the recognizers. One projection fixture cannot qualify all portable syntax.

Pinned campaign backends: Polars 1.42.1, Pandas 2.3.3, PyArrow 25.0.0; core and
plugins move together to the 0.54 line during release preparation. Any pin change
requires fresh affected row/environment evidence. Explicit package dependency
ranges are not adaptive support ranges.

Introduce closed packaged `etlantic.adaptive_qualification/2` data with per-row
signatures, versions, operations/policies, observation references and maturity,
plus `etlantic.adaptive_graduation/1` approval projection. Preserve historical
qualification /1 parsing where needed; no global SUPPORT_MATURITY grants every
row authority. SupportRow serialization retains its existing public shape.

During development, the frozen new signature may run as explicitly Experimental
in development/test mode after normal trust/admission; it is not an Available
or production source claim. Candidate observations do not create approval.
Final release rows require executed matching evidence; unproven rows are absent
from execution authority. Existing 0.53 Experimental policy remains compatible
except necessary explicit pin drift/replanning on upgrade.

Approval records name date, independent reviewer, release owner, exact source/
evidence digests, decision pending/go/no_go, exact row decisions, residual
findings and rollback triggers. Only reviewed go rows may advertise Available,
never above their weakest engine/compiler/source/interchange/runtime/I/O/
environment maturity. A pending record, successful helper or installed provider
cannot approve itself. Package review and existing release attestation supply
trust; hashes alone are integrity, not authentication. No new signing service.

A failed optional row may be removed; failure of the mandatory primary reference
or independent reverse handoff blocks the complete phase go decision. Neither
may be waived through a not-applicable rationale.

### Public Provider Conformance

Export synchronous and asynchronous
`run_adaptive_provider_conformance_suite(cases)` and
`arun_adaptive_provider_conformance_suite(cases)`, plus immutable
AdaptiveConformanceCase/AdaptiveConformanceReport, through etlantic.testing.

Case fields: unique bounded case_id; public PipelineDefinition or Pipeline class;
explicit Profile/RunRequest; isolated runtime_factory; optional context_factory;
mode planning/execution; expected acceptance/rejection and exact expected PM
code; required in-process verify callback for outputs/claims/effects.
Reject empty/duplicate/malformed cases before factories; default helpers do not
write files. Sync inside an active async loop raises RuntimeError; async
cancellation drains the active case and propagates caller cancellation.

Planning uses public validation/plan/fingerprint APIs with zero-effect sentinels.
Execution round-trips the stored plan and invokes the public scheduler.
Unsupported third-party execution remains an expected negative case; unit
protocol/claim fixtures never patch packaged authority to make it positive.
Reuse public compiler/connector/Arrow suites against actual synthetic behavior.

Report schema `etlantic.adaptive_provider_conformance/1` contains passed and
canonical case results: trusted case identifier, mode, expected/observed
acceptance, pass/fail, known code and optional verified fingerprint.
to_dict emits JSON-safe primitives. Harness errors raise ValueError; behavioral
failures return passed=False. Exclude raw exceptions, rows, runtime/Profile,
callables/frames/provider serializers/paths. Provider guide supplies required
positive/negative overclaim, missing/unknown evidence, type, fusion-boundary and
directional interchange cases. Core solver/oracle determinism is a separate
campaign, not a provider obligation. Passing confers no maturity or allowlist
authority; third-party examples require no private core imports.

### Evidence and CI Contract

New `scripts/check_adaptive_0_54.py`:
default executes local frozen cases in temporary storage and emits a safe result,
with no repository/approval writes; `--write --output DIR` retains the actual
complete run including failure; `--verify-index PATH` verifies collected proofs
read-only without pretending to execute remote cells. All return nonzero on
their applicable failure. Writing never emits a go approval automatically.

Observation schema `etlantic.adaptive_observation/1` records actual UTC start/end,
Git commit/tree, normalized source digests before/after, command array, actual
OS/architecture/Python/package versions, CI run/job identity when present,
full parameterized scenario IDs/statuses, exit code and sanitized artifact hashes.
Required skips/xfails/xpasses/deselection/duplicates/missing IDs/backends/zero tests
cannot qualify a row. Source changes during a run invalidate its qualification.

Keep actual environment/time from the generating run. Replay verifies source/
scenario/results/digests, not timestamp equality with a historical run. Never
copy earlier provenance onto a new source digest (#147). Local observations
verify independently of a committed record from a different OS.

Index schema `etlantic.adaptive_evidence_index/1` binds all local ACs, all
**24** program ACs (the old 0.54 plan omitted program AC-024), signatures/cases/
artifacts and actual CI jobs. Graduation cells: Linux/macOS/Windows × Python
3.11/3.12/3.13, observed runner architectures only. Reject missing cells,
cross-source data, invalid/unknown schemas, wrong hashes, escaping paths and
incomplete scenario coverage. Don't execute commands from evidence.
Upload failed environment proof and aggregate with a dependent all-cells job.
Implement and locally test this aggregation; obtaining actual remote cells is
follow-up work, not an implementation completion requirement.

Content digest covers relevant production/packages/types/schemas/tests/fixtures,
scripts/CI/dependency lock/docs/examples and candidate support descriptors;
LF-normalize text and canonicalize paths. Exclude generated observations/index/
decision from their own input digest. Candidate code/descriptor snapshot is
reviewed first; approved packaged projection is bound separately by final CI
at the exact release-candidate commit. This avoids a self-hashing approval cycle
without relabeling a run as occurring at another commit.

Preserve historical evidence. Keep frozen category filenames in the program
gate as phase-0.54 projections and add provider/fusion/differential/operations/
docs/decision reports. Planning artifacts may contribute only to planning ACs.
Fresh qualification never rewrites a historical record into a current proof.

### Operations, Errors and Rollback

Preserve diagnostic ownership and specific existing codes: integrity
PMADP400–429; unsupported consumer/admission PMADP500–519; lifecycle
PMADP520–549, including drift PMADP501, policy PMADP522, cleanup PMADP523,
publication uncertainty PMADP524, stored request/selection drift.
New static source/fusion malformed descriptors use existing integrity/profile
or candidate findings at their owning boundary. Harness errors use safe generic
errors/nonzero status; no new global diagnostic family is needed.

Demonstrate application admission stop, explicit profiles for new work,
quarantine of externally queued stored /2, drain/cancel of active tasks,
native/snapshot cleanup, reconciliation and explicit replanning. A Profile edit
alone does not revoke stored /2. Existing durable/CP workers already reject /2;
no new durable queue, drain API or product kill switch.

Keep uncertain publication receipts/owners; do not blindly retry or delete
published outputs. Retain active checkpoints until drain, invalidate stale
references under recorded policy, and never cross tenant/domain cleanup.
Downgrade repins the entire matching package set and replans explicit work;
stored /2 is never rewritten as /1.

## Invariants, Security and Reliability

Validation and complete admission precede effects. Every applicable production
extension policy authorizes before load. Unknown evidence/source capabilities
never create positive candidates; custom contracts/middleware never silently
lose enforcement through fusion. Source schema validation precedes filtering,
including projected-away columns. Snapshot ownership, adapter pins and all
stored member/port/contract routes survive live registry mutation.

Plans/reports/explain/diagnostics/evidence contain no resolved secrets, source
rows, native handles, raw query/exceptions or provider-controlled serializer
payloads. Compare synthetic outputs in process; retain structural proof only.
The physical DAG schedules work; no runtime re-placement, logical fallback or
stored downgrade. Sink preparation never commits; failure and uncertainty retain
ownership barriers. Normal step-report alias migration stays limited to the
four frozen engine aliases; no global metadata renaming.

Fixed resource limits remain 256 nodes, eight targets/candidates, 2,048 records,
1,000,000 solver expansions, 4 MiB explain and 256 MiB accounted planner state.
New composition and descriptors are accounted before allocation and released on
success/failure. Timing/RSS observations never choose placements.

## Edge Cases and Failure Modes

Existing rows: empty/nullable/valid/invalid contracts; all applicable portable
baseline actions/types; source-only/partial selections, branch/fanout/dual ports;
successful safe retry and unsafe retry rejection; dependency failure, member/run
deadline, cancellation, cleanup failure/abandonment, concurrent runs, definite
write failure, acknowledgement loss and same-destination serialization.
Exercise all seven kinds using existing bounded collection/checkpoint/reuse/
validation descriptors, exact limits/first excess, hit/miss/stale/corrupt/domain
mismatch and repeated operations.

New row: empty file with schema, all-null or absent predicate matches, dropped
required column type mismatch, corrupt/oversized file, row bound first excess,
source/path/adapter drift, symlink escape, snapshot/query cancellation and owner
drain, compile/member-schema/query fault, fused self-edge tamper, alias collisions
in composed IR, scalar parameter range/type mismatch, attempted intermediate
selection/fanout/custom validator/middleware/retry. These must reject or fail at
the named safe boundary without publication.

Planning corpus separately covers multi-source/disconnected/no-solution, same
engine/different target, security/domain boundaries, streaming and expanded
graphs. Positive planning doesn't imply execution authority.
Use fixed permutation seeds 0–15 and process hash seeds 0/1/42; changing eligible
priority is a semantic change, not an invariance test.

Differential comparisons are type-aware and preserve mandated nulls/duplicates/
ordering. Compare public outcomes and dependency/lifecycle constraints; normalize
random identities/durations and unordered independent events. Do not equate True
with 1 or compare only final outputs. Fault wrappers retain real compiler/source/
Arrow effects. Deadline probes synchronize intended boundary entry rather than
assuming startup within 100 ms (#146).

## Acceptance Criteria

Local IDs below are stored with phase 0.54 to distinguish program IDs. Legacy
AC-054-01…06 remain traceable workstream headings: public conformance (001–003),
launch topology (004–008), differential (009–012), security (013–014),
compatibility (015–017), graduation (018–024).

- **AC-001:** Public sync/async conformance models/helpers validate before work,
  return safe behavioral results and preserve async cancellation/drain.
- **AC-002:** Actual compiler/source/fusion/interchange behavior detects overstated
  or unknown claims and independently checks directions.
- **AC-003:** Passing conformance grants no execution/maturity/trust authority;
  third-party fixtures use public imports and isolated optional dependencies.
- **AC-004:** The bounded Parquet adapter validates configuration before I/O,
  snapshots only safe single local files under finite limits, rejects writes,
  and supports independent explicit read behavior.
- **AC-005:** Data-only fusion eligibility proves the exact members, primitive
  contracts, parameter semantics, source capabilities and protected boundaries;
  first unsupported combinations cannot receive optimistic credit.
- **AC-006:** Composed IR and /2 records preserve canonical identities, typed
  member/internal-edge routes, one fused compute mapping and complete external
  dependencies; tampering rejects even after outer fingerprint recomputation.
- **AC-007:** Real pinned Polars query performs predicate/projection at the scan
  and one main composed collection without intermediate eager registration;
  real Pandas dispatch, one Arrow transfer, validation and publication follow.
- **AC-008:** All 14 proposed rows have independent exact-signature proof or an
  explicit removed-row decision; reverse handoff proof is independent, and the
  mandatory reference/reverse cannot be omitted for a full go.
- **AC-009:** Adaptive and explicit runs match contract-shaped outputs,
  validation, selection, logical terminal outcomes and publication across
  applicable empty/nullable/portable corpus.
- **AC-010:** Retry/failure/deadline/cancellation cases preserve attempt fencing,
  upstream attribution and downstream blocking; fused limitations reject safely.
- **AC-011:** Snapshot/native/artifact cleanup drains or records existing owners;
  concurrent invocations and borrowed/shared values remain isolated.
- **AC-012:** Seven-kind boundaries, collection/checkpoint/reuse and publication
  preserve bounds, repeated-operation safety and uncertain receipt reconciliation.
- **AC-013:** Applicable production allowlists and domain denials authorize before
  load; adapter/IR/source/binding/contract/evidence drift rejects atomically.
- **AC-014:** Hostile serializer/query/exception fixtures and recursive scans
  exclude secrets/source rows/native payloads from public/retained artifacts.
- **AC-015:** Ordinary /1 canonical behavior, old readers and valid historical /2
  readability remain compatible; every unqualified consumer rejects before I/O.
- **AC-016:** Class/definition parameter/asset/placement/concurrency/selection
  precedence matches; stored request/selection drift requires replanning.
- **AC-017:** Namespaced step writers and silent legacy report migration preserve
  collision/idempotency rules without renaming unrelated metadata.
- **AC-018:** Oracle/order/hash-seed/parity/resource proofs include new composition
  allocations and exact/first-excess limits under the frozen objective.
- **AC-019:** Fresh observation regeneration preserves actual time/environment/
  commit/scenarios/hashes and cannot fabricate or automatically approve a record.
- **AC-020:** Read-only verification detects missing/skipped/failed/tampered/
  duplicated/cross-source evidence and maps every local and all 24 program ACs.
- **AC-021:** Locally tested aggregation requires nine actual same-candidate
  OS/Python CI records for a cross-platform qualification claim; missing cells
  are reported truthfully. Running remote jobs is not required for handoff.
- **AC-022:** Packaged Available rows derive only from independent reviewed go
  and weakest participating maturity; unproven rows cannot execute in release.
- **AC-023:** Public portable examples/guides/references and finite stop/drain/
  reconcile/replan exercise match the actual matrix and never downgrade stored /2.
- **AC-024:** Pending decision records and locally tested validation support a
  later independent dated decision naming owners, rows, evidence, residual risks
  and rollback trigger; no unresolved in-scope critical/high security,
  correctness, compatibility, data-loss or publication-safety blocker remains.

## Verification Matrix

| Local AC | Preferred proof | Required observation |
|---|---|---|
| 001 | Unit + API + async integration | Imports, pre-factory errors, safe report, drain/cancellation |
| 002 | Real provider contract | Unsupported/overclaim compiler/source/fusion/Arrow cases |
| 003 | Static + negative integration | Public-only provider examples, no authority mutation |
| 004 | Storage integration + security | Safe snapshot/config/schema/bounds/read-only cases |
| 005 | Static analysis + boundary | Eligibility and every first unsupported member/policy/type |
| 006 | Contract/property/tamper | Alpha-renamed composition, internal paths, generated identities |
| 007 | Native e2e | Scan predicates/projection, real calls, one main collect/transfer/receipt |
| 008 | Matrix integration | Each retained row/signature and independent direction |
| 009 | Differential integration | In-process type-aware outputs/validation/lifecycle comparison |
| 010 | Real fault integration | Deadlines/retry/fencing and terminal attribution |
| 011 | Lifecycle + concurrency | Owner/drain/leak sentinels, snapshot and run isolation |
| 012 | Boundary + publication integration | Seven kinds, limits/checkpoints, repeated and uncertain writes |
| 013 | Security integration | Denied-load and zero-effects full-DAG rejection sentinels |
| 014 | Hostile contract + scans | Secret/row/query/serializer canaries and safe evidence |
| 015 | Compatibility/consumer | Explicit goldens, historical readers, pre-I/O rejection matrix |
| 016 | Public integration | Class/definition request capture and precedence/drift |
| 017 | Migration compatibility | Legacy report goldens, collisions, warning-free repeat reads |
| 018 | Oracle/property/boundary | Seeds, limits, new accounted state, explain/diff surface parity |
| 019 | Harness + regeneration | Actual fresh observation provenance and no approval mutation |
| 020 | Tamper/completeness/static | Full pytest IDs, category proofs and program/local mapping |
| 021 | Local aggregation/provenance tests | Accept valid fixture matrix; reject missing/tampered cells; actual remote proof deferred |
| 022 | Local package contract tests | Pending/non-go cannot promote rows; weakest-link checks; actual review deferred |
| 023 | Runnable docs + ops integration | Executed public examples, strict docs/API/CLI/link gates, drain |
| 024 | Local decision validation + scoped findings | Pending record, truthful local evidence, zero implementation blockers; actual #95 decision deferred |

Preserve existing checks.yml lint/format, Pyright, unit/integration,
plugin-manifest, codec burn-in, stable-foundation, surface/diagnostic/protocol,
portable/prior-adaptive/security/packaging/docs gates. Test actual optional
Polars/Pandas/Arrow and isolated core/optional wheels; no new engine in core.
Unrun checks cannot be classified pre-existing failures.

## Implementation Phases — RECOMMENDED IMPLEMENTATION

| Phase | Goal/modules | Behavior/tests/docs | Dependency |
|---|---|---|---|
| 0 | Freeze cases/signatures and ledger; new phase gate | 14-row ceiling, all 24 program/local mappings, full case IDs, exact source/fusion contract and pending decision; update program phase scope to reflect approved extension | Approved scope recorded here |
| 1 | Native source in optional Polars package | AC-004; safe snapshot/read-only/config/schema/bounds/cleanup tests, public factory/registration, manifest evidence and source docs | Phase 0 |
| 2 | Static descriptors/composition/lowering | AC-005–006; optional fusion protocol, original IR storage, identity/alpha-renaming/internal-path tamper, resource accounting, exact objective facts | Phase 1 static descriptor |
| 3 | Whole-DAG admission and fused host | AC-007/010–014; pinned source/compiler/member contracts, native collect, member attribution/deadlines/drain, Arrow/validation/publication; no ordinary node-loop substitute | Phases 1–2 |
| 4 | Public conformance and full qualification | AC-001–003/008–018; existing-row and new-reference differentials, reverse independence, protected failure/security/compatibility/resource suites | Phases 1–3; provider helper can start after descriptors freeze |
| 5 | Fresh evidence/CI aggregation | AC-019–021; actual observations, safe hashes/full IDs, nine-cell aggregation, tamper and provenance (#147) tests; retain failed records | Frozen catalogue and phase 4 |
| 6 | Concepts/provider/API/CLI/migration/operations docs | AC-023; portable examples, precise new source restrictions, rollout/drain/reconcile exercises, current navigation/reference updates | Actual phase 3–4 behavior |
| 7 | Local graduation safeguards and handoff | AC-022/024; validate pending/go/no-go schemas and weakest maturity; local self-check/report. Actual independent review and remote final CI are follow-up work | Passing phases 4–6 |
| 8 | Lockstep release preparation | Core/plugins/manifests/ranges/lock at 0.54.0, isolated wheels, version/docs alignment and affected local requalification; no Available promotion without proof | Local phase 7; tag/publish separate |

Candidate Experimental execution precedes approval; package Available data comes
only after independent review and final CI. Metadata/support changes require
fresh affected proofs rather than hand-edited observation hashes.
Prefer focused additions/extractions; leave unrelated runtime branches alone.

## Risks

| Risk | Control |
|---|---|
| Pushdown hides invalid filtered/dropped input | Validate every raw schema column first; restrict contracts to schema-provable nullable primitives |
| Connected region mistaken for fused realization | Explicit unit subgroup descriptor and real single-query/no-intermediate proof |
| Composition changes ports/lineage or creates self-cycle | Deterministic alpha-renaming and validated internal member routes |
| Native cancellation leaks file/frame owners | Snapshot lifetime follows worker drain and existing cleanup obligations |
| Source change/path escape during query | Safe handle and finite immutable owned snapshot; no cloud/glob/symlink escape |
| One fixture qualifies arbitrary shapes/syntax/providers | Exact source/fusion signature, 14-row ceiling and independent direction/maturity |
| Local conformance becomes self-approval | Non-authoritative report and independently reviewed package projection |
| Evidence regenerated with borrowed provenance | Actual full observation envelope, #147 reproduction, separate final commit proof |
| Deadline verification depends on startup speed | Boundary synchronization and finite real deadlines, #146 |
| Review broadens to every repository issue | Scoped findings and independently reproduced baseline exceptions |

## Explicit Non-Scope

General fusion, alternate filter/projection signatures, Pandas source pushdown,
fusion on other targets/shapes, source connector-session redesign, new engines,
native bodies, SQL/PySpark/DataFusion/DuckDB/remote/resource /2 combinations,
external compilation/orchestration, durable/CP/federated/streaming/expanded /2,
universal costs, runtime replanning/telemetry/speculation, larger solver limits,
distributed transactions, queues/drain APIs, general metadata renaming, database
migrations, authentication redesign and medallion features.

No universal performance guarantee, arbitrary architecture/backend-version
availability, global defect cleanup or enterprise SLA is implied.

## Known Pre-existing Problems and Follow-Up Candidates

Authenticated GitHub open issues were searched and matching issues read.
Reuse existing tracking; no duplicate issue creation is needed.

| Finding | Classification/tracking |
|---|---|
| 0.53 snapshot's source hash changed while retaining earlier provenance | #147: new 0.54 generation/provenance is in scope; preserve historical snapshot and caveat instead of retroactively falsifying it |
| Post-compile deadline test assumes setup within 100 ms | #146: bounded verification fix if reused; preserve actual fencing/drain/no-publication assertions; no demonstrated production deadline redesign |
| Planning Hub/capabilities retain stale/contradictory phase status | #86/#94: required current-0.54 statements/navigation in scope; no global docs rewrite |
| Existing bare logical/report metadata warnings | Follow-up candidate; global renaming out of scope; four step aliases retain scoped compatibility |
| Medallantic fingerprint goldens, FastAPI input redaction, CP list denials, package docstring | Existing #145/#144/#143/#130: outside this local adaptive change unless independently shown to compromise its actual launch path |
| Earlier phase issues remain open despite shipped code | Backlog/evidence housekeeping; not grounds to rebuild shipped subsystems |

Critical/high findings on a retained adaptive path are in scope or require its
removal and go/no-go assessment. Confirm any claimed pre-existing failure on the
unchanged baseline; unrelated defects do not expand this implementation contract.

## Definition of Done

Every locally implementable AC and program behavior has observed local passing
evidence or an explicit applicable rationale. External proof obligations are
identified as deferred follow-up, not classified as implemented remote evidence.
Mandatory reference pushdown/fusion
and reverse handoff cannot be replaced by a not-applicable declaration.
Required compatibility is preserved; no known substantive regression attributable
to this change remains. Locally executable new/existing gates pass except
confirmed, scoped baseline failures that do not make launch behavior unsafe.

Docs/examples and packaged row/maturity data match actually verified behavior.
Graduation stays pending; locally tested safeguards prevent an unsupported
Available claim. The implementation has zero known unresolved in-scope
critical/high correctness, security, compatibility, data-loss or publication-safety
findings. Actual owners, remote observations and independent go/no-go are not
required to complete this handoff.
Luna's passing campaign is not independent approval. The repository need not
be globally defect-free.

## Plan Decision

The scope owner's explicit inclusion of bounded source pushdown and fusion is
reflected in the source, composition, wire, runtime, evidence and verification
contracts. No unresolved architectural decision is delegated to implementation.
Release approval remains contingent on the actual campaigns and independent
decision, not on this plan.

**READY FOR IMPLEMENTATION**
