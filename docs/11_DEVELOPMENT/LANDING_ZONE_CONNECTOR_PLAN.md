# Landing-Zone File Connector Plan

> **Status: Shipped in ETLantic 0.43.0 for snapshot and incremental modes;
> continuous trigger and control-plane composition are in progress for 0.39
> (submitters outside core — thin reference vs CP1 durable API).** See the
> [0.38 exit gate](EXIT_GATE_0_38.md) for connectivity acceptance evidence and
> [ADR-016](adr/ADR-016-CONTROL-PLANE-IDENTITY.md) for CP1 submitter rules.

## Outcome

Authors design **one** logical pipeline with a typed `Extract` and choose how
a periodically populated directory of files (CSV first; Parquet/JSON later) is
consumed:

| Mode | When chosen | Runtime meaning |
|---|---|---|
| **Batch snapshot** | Binding / profile at design or promote time | Each run lists matching files under a Safe I/O root and reads them as one logical extract (deterministic order, contract-validated rows) |
| **Incremental** | Same extract; binding `mode=incremental` + checkpoint | Only new/unprocessed files since the last **successfully committed** cursor advance |
| **Continuous** | Same extract + external/control-plane trigger | A watcher, sensor, or poller submits durable runs when files land; the extract remains snapshot or incremental |

The pipeline graph does not fork into three product types. Mode is a
**capability-selected binding choice**, consistent with
[Extracts](../05_PIPELINES/EXTRACTS.md) (declare what enters; plugins own how).

## Non-goals

- Embedding long-lived daemon loops inside core ETLantic library semantics
- Putting filesystem credentials, absolute host paths, or secret values into
  pipeline definitions or plans
- Silent fallback from incremental to full-folder reread when checkpoints fail
- Claiming multi-tenant isolation for shared landing directories before the
  control-plane gates (0.39–0.43)

## Phase assignment

| Phase | Owns |
|---|---|
| **0.38 — Connectivity / Connector SDK** | Versioned local file landing-zone connector; `batch snapshot` and `incremental` modes; glob/list/read/CSV (and declared formats); checkpoint/cursor; idempotent consume/cleanup; plan-time capability fail-closed; local reference connector for deterministic CI |
| **0.39+ — Control plane & ops composition** | Continuous file-drop → durable run submission (`202` / submitter); tenant/workspace/environment-scoped landing roots and Safe I/O; authorization on trigger and checkpoint stores; later operator visibility of landing-zone lag and failures (toward 0.50) |
| **0.44+ — Developer intelligence (optional UX)** | IDE/workspace explanations of landing-zone binding impact; not a substitute for the connector |

See [ROADMAP § 0.38](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md)
and [Multi-Tenant Control Plane Plan](MULTI_TENANT_CONTROL_PLANE_PLAN.md).

## Authoring model (design-time choice)

```python
from etlantic import Data, Extract, Load, Pipeline, Transformation

class RawEvent(Data):
    event_id: str
    payload: str

landing = Extract[RawEvent](asset="landing_csv")
# ... transforms ...
out = Load[RawEvent](input=..., asset="curated")
```

Binding (secret-free; illustrative — exact schema lands with 0.38 protocols):

```text
asset: landing_csv
provider: local-files   # or etlantic-local-files package name
format: csv
root: inbox             # relative to approved Safe I/O root
glob: "*.csv"
mode: snapshot | incremental
consume: none | rename_done | ledger
checkpoint: …           # required when mode=incremental
```

Trigger policy is **orthogonal**:

```text
trigger: manual | cron | watch | control_plane_sensor
```

`watch` / sensors submit runs; they do not change Extract semantics.

## Capabilities the connector must declare

- `source.batch_snapshot` — list + read matching files in one run
- `source.incremental_cursor` — resume without advancing on uncommitted failure
- `source.file_glob` — deterministic listing under Safe I/O policy
- `format.csv` (initial); optional later `format.parquet` / `format.json`
- `idempotency` / `cleanup` — rename, archive, or ledger so retries do not
  double-commit
- Explicit **absence** of unsupported modes fails at **plan**, not silent
  degrade

## Acceptance scenarios

1. **Batch:** Two CSVs in `inbox/` matching the glob; one run yields the union
   of rows under `RawEvent`. The static plan records the file **identity
   scheme** (algorithm, root ref, listing intent) without enumerating live
   files or retaining row payloads; concrete file identities appear only in the
   run-scoped `LandingReadManifest` and run report.
2. **Incremental:** After a successful run, a new CSV arrives; the next run
   reads only the new file; cursor does not advance if Load fails.
3. **Continuous (0.39+):** A file-drop trigger submits a durable run that uses
   the same logical pipeline and incremental binding; duplicate triggers do not
   corrupt the cursor.
4. **Design switch:** Changing `mode` from `snapshot` to `incremental` in the
   profile/binding re-plans without rewriting transforms; missing capability
   fails closed.
5. **Trust:** Production profiles allowlist the connector package; paths stay
   inside Safe I/O roots; plans/reports remain secret-free and row-free.

## Static plan vs runtime evidence

Ordinary `validate` and `plan` must not list a live directory. A static
`PipelinePlan` records connector selection, listing intent, identity scheme,
capability decisions, config fingerprint, checkpoint reference, and secret
references. Concrete landing-zone file identities belong only in
`LandingReadManifest` and the run report. Any live preflight is an explicit
`inspect` operation. See
[ADR-015](adr/ADR-015-CONNECTOR-PROTOCOLS.md).

## Relationship to shipped 0.37 storage

Today’s `CsvStorage` binds a **single file path**. Landing-zone directory
semantics are **not** an extension of that stdlib helper’s public contract;
they ship as a 0.38+ connector (or successor storage provider protocol) with
conformance suites. See [Storage today](../06_EXECUTION/STORAGE_TODAY.md) and
[Storage Plugin](../07_PLUGIN_SDK/STORAGE_PLUGIN.md).

## Evidence and ownership

| Artifact | Role |
|---|---|
| This plan | Domain outcomes and phase split |
| [ADR-015: Connector protocols](adr/ADR-015-CONNECTOR-PROTOCOLS.md) | Locked protocol, capability, and plan/runtime evidence decisions |
| [0.38 implementation plan](IMPLEMENTATION_PLAN_0_38.md) | Workstreams and quantified exit |
| [Adoption ecosystem plan — DC](ADOPTION_ECOSYSTEM_PLAN.md#data-connectivity-and-connector-sdk) | Program umbrella |
| [ROADMAP § 0.38 / 0.39+](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md) | Release order |
| Connector conformance (future) | Executable proof |

## Out of scope until explicitly gated

- Kafka / queue landing zones (separate connector capabilities)
- Spreadsheet formula-injection hardening beyond SECURITY.md expectations
- Multi-tenant shared inbox without CP isolation keys
