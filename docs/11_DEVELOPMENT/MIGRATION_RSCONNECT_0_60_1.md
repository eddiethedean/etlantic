# Posit Connect adapter migration for 0.60.1

The `etlantic-rsconnect` 0.60.1 candidate works with core 0.60 and fences
external timer resumes with a new owner generation. The published 0.60.0
runner reads its generation only from the bundle configuration, so it cannot
follow a generation change made by the adapter.

Install `etlantic-rsconnect>=0.60.1,<0.61.0` with
`etlantic>=0.60.0,<0.61.0`. Bindings created before 0.60.1 are recognized as
legacy. Resume them with a bundle builder and deployer so the adapter can
upgrade the same Connect content while its timer is paused:

```python
adapter.resume(
    service,
    context,
    schedule_id,
    binding,
    build_bundle=build_bundle,
    deployer=deployer,
    title="ETLantic schedule",
)
```

The `build_bundle` callback receives the paused canonical schedule. Its result
must preserve the schedule ID, revision, current timer generation, receiver
URL, and Connect server. The adapter verifies those values, disarms the
generated content, updates the existing Connect deployment, and records that
the new runner can read the generation environment variable. It then resumes
the canonical schedule, installs its new generation in Connect, creates the
recurrence, verifies it, and arms the content.

If the deployment result is uncertain, inspect the deployment journal and
reconcile the pending binding before retrying. The adapter keeps the canonical
schedule paused until the upgrade and its capability record are confirmed.
