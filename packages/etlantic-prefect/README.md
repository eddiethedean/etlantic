# etlantic-prefect


Version **0.58.0** (lockstep with ETLantic core).
Optional Prefect **ExecutionScheduler** for ETLantic (`etlantic.scheduler/1`).
The local MVP is shipped in ETLantic 0.20.

This is **not** an Airflow-style `compile_plan` / DAG compiler. It coordinates
already-resolved `PipelinePlan` logical nodes via Prefect 3 tasks while ETLantic
owns validation, retries, materialization, and `PipelineRunReport`.

## Install

```bash
pip install etlantic-prefect
```

## Usage

```python
from etlantic import Profile, PipelineRuntime

profile = Profile(name="dev", orchestrator="prefect")
report = MyPipeline.run(profile=profile, runtime=runtime)
```

Local direct invocation only for the shipped 0.20 MVP — no Prefect Cloud/server or
deployment/serve required. Keep `LocalScheduler` (`orchestrator="local"`) as the
default development path.

ETLantic run and step timeouts are enforced by the local runtime; a timed-out
execution fails the outer Prefect flow and retains its ETLantic report. Direct
execution rejects `CancellationPolicy(cooperative=False)` and bounded-abandon
policies during scheduler analysis because those cancellation modes are not
qualified for the in-process path. Managed cancellation is a separate durable
operation and does not infer ETL status from Prefect's remote state.

Managed execution, versioned Process-pool registration, durable dispatch, and
separate remote status/cancellation projections are implemented for phase 0.58.
The clean-wheel integration campaign installs the core, FastAPI, Prefect, SQL,
and SQLModel packages plus a separately built worker-backend wheel into a fresh
environment, then runs Process flows against a self-hosted Prefect API and
PostgreSQL. It covers targeted CSV-to-PostgreSQL and PostgreSQL-to-PostgreSQL
replace-mode transfers, submitter exit, uncertain-create recovery, and a
graceful API restart with persisted flow-run/deployment reads. A live dispatcher
race produces one remote create; two separate Prefect worker runs for one
accepted reference produce one canonical ETLantic attempt and report. A
clean-wheel HTTP/headless parity test also preserves a pinned Prefect route. The
installed-wheel campaign also verifies that a worker fails closed if remote
deployment settings drift after dispatch, and retries that terminal pre-attempt
failure under a new creation generation after the deployment is restored. The
path was qualified against the bounded 0.58.0 release profile; the full scope
and qualification evidence are recorded in the [phase plan](../../docs/11_DEVELOPMENT/IMPLEMENTATION_PLAN_0_58.md).
Production identity providers, independent consumers, external connectors, and
elapsed-time evidence are not phase requirements. Direct scheduler
use remains the local MVP described above. In managed mode,
`PrefectDispatcher` creates a flow run for the registered entrypoint and passes
it a bounded `ManagedExecutionReference`; host applications operate the
dispatcher rather than invoking the flow function directly.
When constructed with a `ManagedBackend`, the dispatcher registers its lifecycle
with that backend. Request drain and join active dispatch work before closing
the backend; a close racing an active tick will refuse to dispose shared stores.
`dispatcher.diagnostics()` provides a provider-free snapshot of process-local
tick failures, create attempts, uncertain creates, missing or failed remote-run
observations, Prefect API failures, and the queue-age high-water mark. It
contains no run identifiers or provider payloads and resets when the dispatcher
process restarts; export it through the host's existing metrics service when
durable or fleet-wide metrics are required.

Before reading leased inputs or beginning connector effects, the worker
reauthorizes the accepted principal for `run.submit`, planned resources, and
input resources, then reevaluates current pre-execution policy and approval.
An approval must remain approved and unexpired at worker claim; revocation or
expiry after acceptance or dispatch fails before connector I/O. The live
Process-worker trace covers revocation on both sides of dispatch and expiry
between dispatch and claim ([partial campaign evidence](../../docs/11_DEVELOPMENT/evidence/phase_0_58/LIVE_APPROVAL_AUTHORITY_BOUNDARIES.json)).
When a separate service identity runs the work, that identity also needs
`run.execute` for the accepted definition. Missing policy for fingerprinted
work and revoked submitter, worker, or approval authority fail closed. The live
Process-worker tests also cover crashes after the durable report event append,
dispatch-process death before create/after create/after link,
cancellation during source staging and terminal report publication, and report
store failure recovery without repeating a committed sink effect. PostgreSQL
retirement tests cover concurrent operators and recovery after process death
between remote pause and durable retirement, including a Prefect API restart at
that exact boundary. A live PostgreSQL campaign leaves a 32-submission backlog
unclaimed across four bounded failed dispatcher ticks while the Prefect API is
stopped, then drains it one item per tick and completes every target once with
a separate Process worker ([campaign evidence](../../docs/11_DEVELOPMENT/evidence/phase_0_58/LIVE_POSTGRES_32_SUBMISSION_OUTAGE_RECOVERY.json)).
A second trace stops the API after the worker commits its effect and report but
before host finalization; the canonical run stays authoritative while remote
status is unavailable, and API restart lets that worker finish publication
without repeating the effect. A separate bounded trace stops the API while a
worker is paused at the PostgreSQL connector-commit boundary, commits one sink
effect with result publication pending, then restarts the API and completes the
same attempt once ([local evidence](../../docs/11_DEVELOPMENT/evidence/phase_0_58/LIVE_CONNECTOR_COMMIT_DURING_PREFECT_API_OUTAGE_2026-10-12.json)).
Process-worker recovery also covers a hard kill during a partial artifact
staging write before atomic replacement, a sink credential rotation after
dispatch but before claim, and a test backend that independently commits a
partial sink row before worker death. Recovery keeps that row, marks the effect
unknown, and does not replay it. This fixture exercises PostgreSQL recovery;
the 0.58 support claim covers only its tested PostgreSQL-backed modes. Other
connectors are outside this phase. Broader in-repository authority-rotation
cases remain listed as local gates; prolonged-outage evidence is not required.

The local clean-wheel campaign passed 44 Prefect tests with no skips and the
headless/FastAPI parity test on Python 3.11.15, Prefect 3.7.8, PostgreSQL 16.13,
the Process worker pool, and ETLantic core/Prefect/FastAPI/SQL/SQLModel 0.58.0
wheels plus the separately built test backend. The earlier blocking CI
clean-wheel job on candidate `7336d377` passed all 44 installed-wheel tests.
GitHub Actions run 38222124256 passed all 46 installed-wheel tests without
skips on Ubuntu 24.04 with CPython 3.11.15, 3.12.13, and 3.13.16, plus installed
headless/FastAPI parity on each patch. It includes the connector-commit/API-
outage trace and approval revocation/expiry checks. The [matrix evidence
record](../../docs/11_DEVELOPMENT/evidence/phase_0_58/CI_INSTALLED_WORKER_PYTHON_MATRIX_2026-10-12.json)
contains runtime manifests, JUnit reports, wheel digests, and artifact hashes.
These versions define the tested support profile. Other Python and Prefect
versions, operating systems, databases, and worker pools are outside the 0.58
support claim and do not require qualification evidence for this phase.
The expanded restricted-role PostgreSQL test also completes versioned
deployment registration, routed acceptance, and remote dispatch create/link
using table DML grants without schema `CREATE` privilege.
The [phase 0.58 evidence ledger](../../docs/11_DEVELOPMENT/evidence/phase_0_58/RELEASE_INDEX.json)
tracks the remaining qualification work.

The local clean-wheel run also passed the partial-effect and mid-execution API recovery traces. The exact local clean-wheel environment was:

| Component | Exercised version/configuration |
|---|---|
| OS and architecture | macOS 26.5.2, arm64 |
| Python | CPython 3.11.15 |
| ETLantic packages | core, Prefect, FastAPI, SQL, and SQLModel 0.58.0 |
| Prefect server and worker | Prefect 3.7.8, self-hosted API, Process pool |
| PostgreSQL | 16.13 for the control plane and Prefect API database |
| SQL clients | SQLAlchemy 2.0.51, psycopg 3.3.4, asyncpg 0.31.0 |
| HTTP/headless parity | FastAPI 0.139.2 with a pinned Prefect execution route |

| Managed capability | Current evidence and boundary |
|---|---|
| Plan and envelope | Static-batch `etlantic.plan/1` through `etlantic.execution_envelope/2`; adaptive `etlantic.plan/2` is rejected before connector I/O. |
| Data paths | Live Process-worker CSV-to-PostgreSQL and PostgreSQL-to-PostgreSQL replace-mode runs. Other connectors and writer modes are outside the 0.58 support claim. |
| Worker pool | Process pool is the only accepted pool and was exercised in the recorded environment; other pool types are rejected at registration. |
| Prefect hosting | Self-hosted API with PostgreSQL persistence. Prefect Cloud, Docker, Kubernetes, and other pools have no managed support claim. |
| Host composition | Headless and FastAPI command parity passed from installed wheels. Posit Connect is a deployment recipe, not a live-qualified host. |
| Qualification boundary | The published 0.58.0 profile is Ubuntu 24.04, CPython 3.11.15/3.12.13/3.13.16, Prefect 3.7.8, PostgreSQL 16.15, and the Process pool. Other combinations are unsupported. No production identity provider, third-party connector, external consumer, live Posit host, prolonged outage, sustained production-capacity, or elapsed-time evidence is required; no claim is made for them. |

The same scoped reference can read ETLantic's canonical run projection or
persist an authorized ETLantic cancellation:

```python
from etlantic_prefect import (
    get_managed_run_status,
    request_managed_run_cancellation,
)

status = get_managed_run_status(reference.to_dict())
cancel = request_managed_run_cancellation(reference.to_dict())
```

Status returns ETLantic's canonical `status` alongside a separately timestamped
`remote_orchestration` observation. Cancellation is durable in ETLantic before
the adapter asks Prefect to cancel a correlated flow run; its
`remote_cancellation` result is separate from canonical ETL status. Neither
adapter infers ETL success or rollback from Prefect state.

The reference contains only submission identity and integrity fingerprints.
The worker backend must be installed as a unique entry point in the
`etlantic.prefect_worker_backends` group and return a
`(ManagedBackend, ControlPlaneContext)` pair from trusted deployment
configuration. Run parameters cannot select this factory or supply a backend
configuration.

Register a versioned deployment only after reviewing a read-only preview. Hash
the dependency lockfile from the exact worker environment, then pass that
digest into the typed specification:

```python
import asyncio
import hashlib
from pathlib import Path

from etlantic_prefect import ManagedDeploymentSpec, PrefectDeploymentRegistrar

lock_sha256 = hashlib.sha256(Path("uv.lock").read_bytes()).hexdigest()
spec = ManagedDeploymentSpec.from_current_runtime(
    name="daily-load",
    work_pool_name="etlantic-process",
    worker_backend_entry_point="production_backend",
    lockfile_sha256=lock_sha256,
)
registrar = PrefectDeploymentRegistrar()

async def provision():
    preview = await registrar.preview(spec)
    return await registrar.register(
        spec,
        expected_fingerprint=preview["spec"]["fingerprint"],
    )

binding = asyncio.run(provision())
```

Registration refuses non-Process pools, fingerprints the installed source and
package versions, creates an immutable versioned deployment with no schedules
or default parameters, injects only the verified worker binding, and resumes it
after verification. The API-side `SQLModelBackendConfig` must use
`execution_route=binding.execution_route`; that trusted setting pins every new
acceptance to this deployment. Existing accepted work keeps its original route.
The worker process reconstructs the binding from deployment-owned environment
and the dispatcher verifies remote deployment and pool configuration before
claiming work.
To roll back new admissions, explicitly re-register the previously reviewed
immutable specification and point the API-side service back to that binding;
accepted work remains pinned to its original route. For retirement, grant the
deployment operator the dedicated `execution.route.manage` authorization, then
call:

```python
result = await registrar.retire(
    binding,
    backend=backend,
    context=ctx,
    expected_fingerprint=binding.fingerprint,
)
```

It atomically changes the route from `active` to `draining`, which rejects new
accepts while allowing dispatch and workers to finish the already accepted
queue. The bounded durable workload
counts cover active submissions, attempts, dispatch intents, unresolved effects,
pending result publications, and unacknowledged outboxes across the shared
durable store. The registrar also checks for nonterminal Prefect flow runs. It
returns `draining` while any of that work remains; repeat the operation after
the work finishes. Once clear, it pauses and retains the immutable deployment,
then changes the route to `retired`. Retirement keeps the paused deployment
and its history.
New schedules reserve their Prefect route durably, so a route cannot retire
while a live schedule still points to it. Move the schedule to another active
route or delete it through the authorized schedule service before retrying
retirement.

An operator may remove an unused retired deployment with `registrar.cleanup`.
The default retention is 30 days after retirement. Controlled-clock boundary
tests verify time-based behavior; no wall-clock delay or retention interval is
required as phase evidence. Cleanup requires no
canonical submission history, no schedule records or reservations, the exact
paused Process binding, and no Prefect flow run in any state. It records a
durable `cleanup_pending` fence before deletion, so reactivation is refused
after cleanup starts. If Prefect deletes the deployment but the response is
lost, retrying cleanup observes the missing exact deployment and finalizes the
route as `cleaned`. Cleanup never deletes Prefect flow-run history; a deployment
with any such history remains retained.
Finalized cancellation clears a pending or already exhausted pre-claim dispatch;
leased and ambiguous creates remain outstanding until remote state is resolved.

`PrefectDeploymentRegistrar.reactivate(...)` verifies the retained deployment
and Process pool, resumes the deployment, and then reopens admissions on the
route. Route lifecycle revisions and the latest 64 operator transitions are
stored with the durable snapshot, and a lifecycle event is appended when the
event provider supports it. The route lifecycle is store-wide, so all API and
worker processes that share its SQLModel `store_id` see the same admission
gate. Retirement/rollback still needs live multi-process and PostgreSQL fault
qualification before release.

The deployment binding produces the route fingerprint. The API-side backend
configuration and dispatcher use that same value. A bounded dispatcher tick
can create or recover flow runs for the route and persist their Prefect run IDs:

```python
from etlantic_prefect import PrefectDispatcher

dispatcher = PrefectDispatcher.from_environment(
    backend,
    context,
    owner_id="dispatch-host-01",
)
receipts = await dispatcher.tick(limit=20)
```

The registrar injects the trusted deployment ID, route, backend entry point,
and versioned specification into the deployment environment. The API-side
dispatcher is built from the same trusted environment, retries uncertain
creates with the same durable idempotency key and bounded backoff, and does not
acknowledge ETL execution or result publication. Run it as a separately
supervised process. Its `status()` is a cached local readiness snapshot and
`request_drain()` stops new ticks and claims; callers own process lifetime and
polling cadence.

Each dispatcher tick also inspects a bounded page of linked runs for terminal
Prefect failures and missing flow-run records. A route-scoped identity cursor
advances across pages and wraps at the end so a persistent first page does not
starve later dispatches; the cursor resets when the dispatcher process restarts.
A failed or crashed run can be
rearmed only when the exact linked ID matches, the canonical submission is
still accepted, and the durable store confirms that no active execution lease,
attempt, effect, or result publication exists. A `404`/missing run must remain
missing for the configured grace interval (300 seconds by default, measured
from the durable dispatch update) before it can be rearmed under the same
pre-execution checks. Set `missing_run_grace_seconds` on the dispatcher to a
value from 30 to 86400 seconds when constructing it. Each rearm has a distinct
creation key and automatic generations are capped at three. Ambiguous create
responses continue with the original idempotency key; failures after ETLantic
execution begins are never replayed automatically. When the automatic limit is
reached, the dispatch moves to `reconciliation_required`, remains visible in
the authorized status projection with its failed/missing Prefect observation,
and is excluded from dispatcher claims. An operator can use
`ManagedApplicationService.rearm_exhausted_prefect_dispatch` with the
`execution.dispatch.reconcile` permission, the exact generation and flow-run
ID, and a bounded evidence note. The durable transition rechecks that the
route is active and that no canonical lease, attempt, effect, or publication
exists. It records the actor and a digest of the redacted note in dispatch
history and emits `execution.dispatch_reconciled`; the note itself is never
stored. Stale requests conflict, and route retirement stays blocked until the
operator rearms or cancels the unresolved acceptance.

The managed adapters are governed by
[ADR-027](https://github.com/eddiethedean/etlantic/blob/main/docs/11_DEVELOPMENT/adr/ADR-027-MANAGED-PREFECT-EXECUTION.md).
The managed adapter is implemented in the current 0.58 release under
[phase 0.58](https://github.com/eddiethedean/etlantic/blob/main/docs/11_DEVELOPMENT/IMPLEMENTATION_PLAN_0_58.md)
and [#290](https://github.com/eddiethedean/etlantic/issues/290) through #298;
the bounded static-batch `/1` Process-worker/PostgreSQL profile is qualified for
the published 0.58.0 release. It is not available in the 0.57.2 distribution.
See the [final
qualification decision](https://github.com/eddiethedean/etlantic/blob/main/docs/11_DEVELOPMENT/evidence/phase_0_58/FINAL_QUALIFICATION_DECISION_2026-10-12.json).
The target is static-batch `/1`, self-hosted Process workers, and PostgreSQL;
other managed capabilities require their planned qualification.

## Decision table

| Path | Protocol | Package |
|---|---|---|
| Local in-process | `ExecutionScheduler` | built-in |
| Prefect direct execution | `ExecutionScheduler` | `etlantic-prefect` |
| Airflow DAG artifacts | `OrchestratorPlugin` / `compile_plan` | `etlantic-airflow` |

## Links

[Prefect example](https://etlantic.readthedocs.io/en/v0.58.0/09_EXAMPLES/PREFECT_RUN/) ·
[Source](https://github.com/eddiethedean/etlantic/tree/main/packages/etlantic-prefect) ·
[Issues](https://github.com/eddiethedean/etlantic/issues)
