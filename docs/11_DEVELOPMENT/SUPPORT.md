# Support Policy (maintainers)

> **Status: Available in ETLantic 0.46.0.**

> **Canonical adopter policy:** root
> [`SUPPORT.md`](https://github.com/eddiethedean/etlantic/blob/main/SUPPORT.md).
> Keep this page as maintainer extras only; do not duplicate pin/envelope text.

ETLantic **0.46.x** is a **Beta** release. Community support is
best-effort with **no formal SLA**.

## Where to ask

- Bug, documentation problem, or feature request: GitHub issue
- Usage question: GitHub issue or discussion when enabled
- Security vulnerability: follow the private process in `SECURITY.md`

Include the ETLantic version, Python version, operating system, installed
plugin versions, exact command, diagnostic code, and a minimal reproduction.
Remove credentials, customer data, internal hostnames, and production plans.

## Maintainer notes

- The current published minor line (`0.46.x`) receives best-effort correctness
  and security fixes. Older 0.x lines are not actively maintained.
- Multi-tenant isolation remains outside the current **0.39** single-tenant
  envelope (CP1 incubates identity/API only; see
  [MULTI_TENANT_CONTROL_PLANE_PLAN](MULTI_TENANT_CONTROL_PLANE_PLAN.md)).
- Experimental APIs (including `etlantic-datafusion`) and Future design pages
  carry no support guarantees.

## What maintainers may close

Maintainers may close reports that cannot be reproduced, omit requested
version information, depend on an unsupported backend, expose sensitive data,
or request behavior explicitly listed as future design.

Community support does not replace adopter ownership of deployment,
monitoring, recovery, and backend operations outside the documented
reference envelope.
