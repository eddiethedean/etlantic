# Support Policy (maintainers)

> **Status: ETLantic core 0.60.0 is a Beta candidate; 0.59.x remains the published support line. The independent `etlantic-rsconnect` 0.60.0 preview is published without production support qualification.**

> **Canonical adopter policy:** root
> [`SUPPORT.md`](https://github.com/eddiethedean/etlantic/blob/main/SUPPORT.md).
> Keep this page as maintainer extras only; do not duplicate pin/envelope text.

ETLantic **0.59.x** is the latest **published core Beta** line. The
`etlantic-rsconnect` 0.60.0 preview has no live Connect activation or production
support qualification. Community support is best-effort with **no formal SLA**.

## Where to ask

- Bug, documentation problem, or feature request: GitHub issue
- Usage question: GitHub issue or discussion when enabled
- Security vulnerability: follow the private process in `SECURITY.md`

Include the ETLantic version, Python version, operating system, installed
plugin versions, exact command, diagnostic code, and a minimal reproduction.
Remove credentials, customer data, internal hostnames, and production plans.

## Maintainer notes

- The latest published line (`0.59.x`) receives best-effort correctness
  and security fixes. Older 0.x lines are not actively maintained.
- Supported isolation profiles (`isolated-deployment`, `dedicated-schema`)
  graduated in 0.43. There is no hosted multi-tenant SaaS. See
  [MULTI_TENANT_CONTROL_PLANE_PLAN](MULTI_TENANT_CONTROL_PLANE_PLAN.md).
- Experimental APIs (including `etlantic-datafusion`) and Future design pages
  carry no support guarantees.

## What maintainers may close

Maintainers may close reports that cannot be reproduced, omit requested
version information, depend on an unsupported backend, expose sensitive data,
or request behavior explicitly listed as future design.

Community support does not replace adopter ownership of deployment,
monitoring, recovery, and backend operations outside the documented
reference envelope.
