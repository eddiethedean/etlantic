# etlantic-aws

Optional EventBridge Scheduler delivery and ECS/Fargate execution over
ETLantic's public trigger, accepted-work, and durable-dispatch contracts.
Install `etlantic-aws[aws]` on the control host for boto3. The worker image
installs `etlantic-aws` and the configured runtime/provider plugins; it does not
need boto3 or Prefect.

Scheduling and execution are configured independently. `EventBridgeScheduler`
only creates disabled schedules and compares complete remote readback before
activation. A caller must first register the external timer owner and persist the
schedule through `ScheduleApplicationService`, including
`timer_binding_fingerprint=adapter.binding_fingerprint`. The fingerprint covers
the account, region, schedule group, pinned Lambda version, invocation role,
DLQ, and retry limits; the schedule record keeps it with its revision, owner
generation, recurrence, and stable start anchor. The remote name is derived from
the schedule ID, and every mutation checks full readback before changing state.
Supply `mutation_guard` to serialize the full readback/write/readback sequence
across scheduler processes. With the SQLModel provider, pass
`lambda record: schedule_store.timer_mutation_lock(ctx, record.schedule_id)`;
this uses PostgreSQL session advisory locks and fails closed on other dialects.

`ScheduledTriggerRelay` validates Scheduler context against a fresh durable
schedule lookup and delegates delivery to the shared bounded
`etlantic-rsconnect` HTTPS transport. Point Lambda at
`etlantic_aws.relay.lambda_handler`, set `ETLANTIC_AWS_SCHEDULE_RELAY` to an
installed factory name, and register that factory in the
`etlantic.aws_schedule_relays` entry-point group. The factory returns a relay
configured with the canonical schedule lookup and credential resolver. Configure
the Scheduler retry/DLQ and Lambda asynchronous retry/on-failure destination as
separate failure paths.

Create the canonical external schedule, call `create_disabled(record)`, verify
the record and AWS readback, then call `activate(record)`. After a pause, resume
through `ScheduleApplicationService`; it increments the timer generation and
sets a fresh anchor. Pass the paused and resumed records to
`update_disabled(previous, resumed)`, then activate the resumed record. An
overdue cursor fails closed and must be re-anchored before activation. Changing
the AWS target binding requires a separately reviewed migration.

`ECSExecutionBinding` pins one Fargate cluster, task-definition revision, image
digest, roles, worker entry point, Linux/X86_64 platform, and private network. The
`ECSDispatcher` submits only a 4 KiB accepted-work reference, persists dispatch
intent first, and uses the same RunTask token and request after uncertain
responses. `ECSWorker` loads its backend through the `etlantic.ecs_worker_backends`
entry-point group and executes only the matching accepted submission through
the canonical managed backend.

AWS resources, IAM, networking and PostgreSQL are supplied by the operator. The
package does not create infrastructure or secrets. See the phase 0.61
implementation plan for the bounded support matrix and live qualification gates.
