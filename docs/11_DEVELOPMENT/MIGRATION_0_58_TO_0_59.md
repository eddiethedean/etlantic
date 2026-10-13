# Migration from ETLantic 0.58 to 0.59

ETLantic 0.59 consolidates the managed SQLModel configuration and schedule
services, adds provider-neutral durable dispatch fields, and introduces the
versioned external schedule trigger contract. This guide describes the source
migration; production support remains subject to the 0.59 exit evidence.

## Choose the managed install

For a headless worker, scheduler, or CLI process, install the explicit extra:

```bash
pip install 'etlantic[managed-headless]>=0.59.0,<0.60.0'
```

This installs the SQLModel backend and PostgreSQL driver without FastAPI. For
an HTTP process, keep using the existing adapter extra:

```bash
pip install 'etlantic-fastapi[managed]>=0.59.0,<0.60.0'
```

The HTTP extra retains its existing meaning. Host applications continue to
derive `ControlPlaneContext` from trusted authentication and provide an
`Authorizer`; neither a route parameter nor the trigger body supplies scope.
The headless constructor accepts the same 25 shared settings as the FastAPI
configuration. Injected engines remain caller-owned, and a configured URL
cannot be combined with an injected engine.

## Preserve the database boundary

Take a database backup before changing package versions. Apply the SQLModel
migrations explicitly before starting a 0.59 process:

```python
from sqlalchemy import create_engine
from etlantic_sqlmodel.migrations import upgrade

engine = create_engine(database_url)
try:
    upgrade(engine)
finally:
    engine.dispose()
```

Managed constructors and schema inspection remain read-only. Durable work is
written through `MemoryDurableWorkStore.to_snapshot()` and decoded through its
versioned snapshot API. Existing 0.58 Prefect records retain their route,
binding fingerprint, remote run ID, and reconciliation history. The SQLModel
snapshot keeps a legacy top-level projection for rollback of representable
Prefect work. External-timer-owned schedule snapshots deliberately fail closed
in a 0.58 reader; transfer those schedules back to local ownership or keep a
0.59-compatible reader before rolling back. Do not manually edit snapshot JSON.

## Configure external timer ownership

Local polling remains the default. An external timer is admitted only for a
managed durable schedule with a bound workload identity and the
`schedule.bind_external_timer` authorization. The timer sends the exact next
scheduled UTC occurrence, schedule revision, and owner generation. It derives
the occurrence ID with the public `external_occurrence_id()` helper and sends
only the versioned envelope; parameter values, secrets, pipeline code, profile
settings, URLs, and credentials stay in the registered backend.

The receiver authorizes `schedule.trigger` before looking up a schedule or
occurrence. It returns a pending receipt while another receiver owns the
preparation lease with HTTP 202, and retries resolve to the same firing and
status URL. The OpenAPI document publishes the bounded envelope schema. A new
delivery must match the stored next-fire cursor and cannot arrive more than 60
seconds early. Firing receipts are retained durably without automatic
compaction in 0.59, so old retries resolve to the original occurrence. Use
the timer-owner transfer operation with the expected schedule revision and
generation. An unlinked occurrence must finish or be recovered before the
timer authority can move or the schedule can be deleted. The generation
increases on every transfer; the
occurrence ID remains derived from schedule ID, revision, and nominal time.

## SparkForge compatibility

Importing `etlantic-sparkforge` now emits a visible migration warning. Install
and import `medallantic` instead. ETLantic 0.62.0 is the final compatibility
release; routine release publication stops in 0.63 after the migration window.
