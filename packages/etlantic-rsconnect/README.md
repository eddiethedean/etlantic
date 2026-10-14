# etlantic-rsconnect

Optional Posit Connect deployment, schedule, and HTTPS trigger integration for
ETLantic. The generated Quarto content contains a small standard-library runner;
it does not install FastAPI, Data Mover, ETL engines, pipeline definitions, or
source and sink credentials.

Install the package and optional Posit SDK with:

```bash
pip install 'etlantic-rsconnect[connect]'
```

The deployment host also needs Quarto and `rsconnect-python` 1.31.1 or newer.
Those are external deployment tools, not runtime dependencies of this Python
package. `RsconnectPythonDeployer` targets one explicit HTTPS Connect URL. It
resolves separate deployment and trigger credential references only at the
authorized boundary, passes values through the child environment, and never
puts credentials in command arguments or surfaced CLI output. Supply a durable
`DeploymentJournal`; a timed-out or ambiguous publish is recorded as uncertain
and must be reconciled before retrying.

`build_trigger_bundle` creates a deterministic Quarto project whose pre-render
hook runs the standalone delivery script on every render. The archive includes
the explicit receiver URL, schedule references, outbound bounds, and a secret
reference, but no credential value. The bundle keeps execution caching off and
an empty, comment-only `requirements.txt`, so deployment does not infer the
ETLantic development environment as content dependencies. The deployer sets
`ETLANTIC_TRIGGER_ARMED=false` during publish, so build and deployment renders
do not submit a trigger.

The receiver client uses public `etlantic.control_plane` trigger/1 values and
`etlantic.outbound` policy. It pins HTTPS connections to the resolved,
policy-checked addresses; rejects redirects; enforces bounded attempts, elapsed
time, and response bytes; validates exact receipt schema and correlation; and
retries the same occurrence. `reconcile()` looks up the retained receipt for
that same occurrence after an uncertain delivery. A missing receipt returns
`None`; callers may retry with the same envelope, never a newly derived slot.
`OccurrenceContext` must come from a trusted integration and contains canonical
scheduled UTC time plus stable delivery-attempt and correlation identifiers.
Public limits cap a delivery at 10 attempts, 60 seconds per request, 300 seconds
total, 1 MiB of response data, and 60 seconds of `Retry-After` delay; the
defaults are 3 attempts, 10 seconds, 30 seconds, 64 KiB, and 5 seconds.

The elapsed budget includes DNS, credential lookup, and response reads. Secret
resolvers run in background threads with the caller's contextvars and must
support that calling convention. Timed-out results are discarded. Each process
allows at most four outstanding DNS workers and four credential workers; a
saturated resolver fails closed rather than creating more workers.

`PositSdkGateway` wraps the public Posit Python SDK schedule and content
environment surfaces. Schedule mutations are experimental, so
`ConnectScheduleAdapter` refuses them unless
`allow_experimental_schedule_api=True` is explicitly set. The adapter requires
a durable, full-record compare-and-swap `BindingStore`, journals pending
mutations before Connect writes, disables the generated content before timer
changes, and retains pending state after uncertain results. Binding stores
must make compare-and-swap atomic across processes. A pending registration is
explicitly marked in its operation metadata. A claimed pending operation
cannot be taken over; a retry only finalizes it when Connect readback proves the
exact requested state. Unfinished or mismatched operations stay pending for
operator reconciliation. It supports the
UTC interval subset exactly representable by Connect's minute, hour, and day
schedule types. For new content, deploy first, pass the successful deployment
result and bundle to `register_deployed_content()`, then call `apply()` with
the returned pending binding. Registration rejects content that already has a
schedule; activation verifies Connect's resulting rule before arming the
content. `inspect_drift()` is read-only and reports when the SDK's decoded
recurrence cannot be compared.

**The generated bundle cannot currently be activated as an ETL trigger.** The
documented Connect scheduled-render path does not provide a trusted nominal
slot and retry identity, and the package does not invent one from render time or
static environment variables. The generated runner therefore refuses delivery
when armed because no qualified occurrence-context provider is in the bundle.
The experimental schedule API, durable ownership/journal implementations,
independent receiver and worker, and live Connect lifecycle also remain
unqualified. These are production support qualification items, not prerequisites
for distributing the package as a preview. The preview does not claim active
scheduled delivery or production support.

See the [0.60 implementation plan](../../docs/11_DEVELOPMENT/IMPLEMENTATION_PLAN_0_60.md)
and [Connect integration plan](../../docs/11_DEVELOPMENT/ETLANTIC_RSCONNECT_PLAN.md)
for the remaining platform decisions and evidence gates.

The [local simulation design](../../docs/11_DEVELOPMENT/CONNECT_SIMULATION_DESIGN_0_60.md)
records SDK, scheduling, HTTPS, and crash-recovery simulations that run without
a Connect server. The regression suite covers SDK recurrence normalization,
resume-anchor preservation, bounded DNS and credential resolution, and actual
verified loopback TLS deadlines through closing-response handoff. Live
Connect qualification remains relevant to production support claims, not package
distribution.
