# Scheduler and worker

> **Status: Available in ETLantic 0.48.0.** Budget ~15 minutes after
> [Quickstart](QUICKSTART.md). PyPI only — local JSON stores, no FastAPI.

Schedules are secret-free timers that wrap durable work. They never embed
payloads or secret values. Overlap defaults to **skip**.

## 1. Create a schedule

From the Quickstart project directory:

```bash
python -m etlantic schedule create \
  --store schedules.json \
  --definition-id SamplePipeline \
  --interval 60
```

Expected: JSON for one interval schedule (`kind` `interval`,
`interval_seconds` 60) and a `schedule_id`. Copy that id for the next
commands (shown as `SCHEDULE_ID`).

```bash
python -m etlantic schedule list --store schedules.json
python -m etlantic schedule preview SCHEDULE_ID --store schedules.json
```

`preview` prints the next fire time. It does not run the pipeline.

## 2. Tick the scheduler once

```bash
python -m etlantic scheduler serve --store schedules.json --once
```

Expected: JSON with `"claimed"` (due firings claimed this tick) and
`"ready"`. The scheduler writes durable work next to the store
(`schedules.durable.json` by default). Production must not colocate this
process with the FastAPI gateway.

## 3. Tick the worker once

```bash
python -m etlantic worker serve --durable-store schedules.durable.json --once
```

Expected: JSON listing processed durable work. The worker never imports
FastAPI. If nothing was due, `claimed` / processed lists can be empty — that
is success.

## 4. Pause and policies

```bash
python -m etlantic schedule pause SCHEDULE_ID --store schedules.json
python -m etlantic schedule resume SCHEDULE_ID --store schedules.json
```

Overlap is `skip`: a fire that is already running is skipped, not queued.
Misfires and fires outside the effective window are also skipped. See
[What's new in 0.47](WHATS_NEW_0_47.md) and
[CLI — schedule](../10_REFERENCE/CLI.md#schedule).

## What this is not

- Not a replacement for Airflow/Dagster ops UIs.
- Not a hosted multi-tenant scheduler.
- Live remote federation extras (`etlantic-k8s`, `etlantic-spark-connect`)
  remain Experimental.
