# Support Policy

ETLantic **0.21.x** is production/stable for documented single-tenant
reference deployments. Community support is best-effort and provides **no
formal SLA** or guaranteed response time.

## Where to ask

- Bug, documentation problem, or feature request: GitHub issue
- Usage question: GitHub issue or discussion when enabled
- Security vulnerability: follow the private process in `SECURITY.md`

Include the ETLantic version, Python version, operating system, installed
plugin versions, exact command, diagnostic code, and a minimal reproduction.
Remove credentials, customer data, internal hostnames, and production plans.

## Supported versions

The current published minor line (`0.21.x`) receives best-effort correctness
and security fixes. Older 0.x lines (including **0.19.x**) are not actively
maintained. See `SECURITY.md` for the security-support table.

## Adopter-owned and unsupported areas

- Production incident response or on-call coverage
- Multi-tenant isolation and deployment topology
- Compliance attestations (SOC2, GDPR certification, and similar)
- SBOM/signing and advanced supply-chain controls beyond documented package
  pins and plugin allowlists
- Guarantees for Experimental APIs (including `etlantic-datafusion`)
- Guarantees for Future design / Design Proposal pages

## What maintainers may close

Maintainers may close reports that cannot be reproduced, omit requested
version information, depend on an unsupported backend, expose sensitive data,
or request behavior explicitly listed as future design.

Community support does not replace adopter ownership of deployment,
monitoring, recovery, and backend operations outside the documented
reference envelope.
