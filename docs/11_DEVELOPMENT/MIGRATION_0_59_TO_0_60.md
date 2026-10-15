# Migration from ETLantic 0.59 to 0.60

ETLantic 0.60 is a core Beta candidate that adds public durable-dispatch
contracts for the optional 0.61 AWS adapter. The candidate is not published;
0.59.x remains the supported core line until a 0.60 release is recorded.

## Package compatibility

The candidate core and first-party plugins use the 0.60.0 package line. The
`etlantic-aws` 0.61 adapter requires `etlantic>=0.60.0,<0.62.0` and
`etlantic-rsconnect>=0.60.0,<0.62.0`. Do not install the AWS candidate with a
0.59 core package: the accepted-work and durable-dispatch APIs it imports are
introduced in core 0.60. The already-published `etlantic-rsconnect` 0.60.0
preview remains compatible with `etlantic>=0.59.0,<0.61.0`.

## Durable state and rollback

The core dispatch snapshot advances from schema `/4` to `/5` to persist the
start of an ECS client-token window. The decoder continues to read `/4` and
legacy snapshots. SQLModel stores use the same public snapshot codec; this
change adds no SQL DDL migration. Back up durable state before upgrading and
keep older processes from writing while a newer process owns ECS dispatches.
An older process cannot safely interpret new ECS state and must fail closed.

If an ECS `RunTask` response is uncertain beyond the safe token window, the
dispatcher quarantines the work rather than issuing a new token. An operator
may rearm an ECS dispatch only after the canonical reconciliation path has
recorded evidence and authorized a new generation. Prefect rearm still
requires its known remote run identity.

## AWS qualification boundary

The local adapter implementation does not qualify live EventBridge Scheduler,
Lambda, ECS/Fargate, IAM, networking, or PostgreSQL behavior. Keep AWS
activation disabled until the independent qualification and support decisions
in the [0.61 implementation plan](IMPLEMENTATION_PLAN_0_61.md) are complete.
