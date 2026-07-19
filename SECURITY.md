# Security Policy

ETLantic 0.18.0 is **stable** for documented single-tenant reference
deployments (not unrestricted enterprise production). Security reports
concerning the published package, contract loading, planning, local runtime,
storage bindings, secret handling, dataframe, SQL, and PySpark plugins,
documentation, or repository automation are welcome.

## Supported Versions

| Version | Support |
|---|---|
| 0.18.x | Current supported stable line; security fixes are released on this line |
| 0.17.x and earlier | Not actively maintained; upgrade to 0.18.x |

Backports to older minor lines are not provided. Upgrade to the latest 0.18.x
patch before reporting an issue.

## Reporting a Vulnerability

Do not open a public issue for a suspected vulnerability.

**Use GitHub private vulnerability reporting** for this repository
([Security advisories](https://github.com/eddiethedean/etlantic/security/advisories)).
If private reporting is temporarily unavailable, contact the maintainer listed
in [MAINTAINERS.md](MAINTAINERS.md) and request a secure channel before sending
sensitive details.

Include:

- Affected version and component
- Security impact
- Minimal reproduction steps
- Relevant non-secret configuration
- Suggested mitigation, when known

Never include production credentials, customer data, regulated records, or
live exploit targets.

## Scope

Security-sensitive areas include:

- Unsafe contract or configuration parsing
- Path traversal
- Arbitrary code execution outside explicitly registered implementations
- Secret disclosure in plans, logs, reports, exceptions, or generated files
- Storage binding and plugin supply-chain vulnerabilities
- Cross-run artifact, cache, or report exposure
- Injection vulnerabilities, including SQL identifier and parameter handling
  in SQL plugins (structured compilation and bound parameters; untrusted raw
  SQL is out of scope)

The detailed threat model is documented in
[docs/02_FOUNDATIONS/SECURITY.md](docs/02_FOUNDATIONS/SECURITY.md).

## Severity (informal)

| Severity | Examples |
|---|---|
| Critical | Remote code execution, credential exfiltration from plans/logs |
| High | Privilege escalation via plugins, path traversal writes |
| Medium | Fail-open trust controls, secret leakage in edge diagnostics |
| Low | Hardening gaps without practical exploit path |

## Disclosure

The project follows coordinated disclosure: acknowledge the report, assess
impact, prepare and test a fix, publish an upgrade, and then disclose technical
details at an appropriate time.

Target acknowledgement is seven days when possible. This is a target, not an
SLA, and CVE assignment is not guaranteed.
Patch ownership sits with the lead maintainer ([MAINTAINERS.md](MAINTAINERS.md)).
If a release token is compromised, revoke it immediately, yank affected
artifacts if necessary, and publish a replacement after rotating credentials.

## Residual deployment responsibilities

The stable support boundary does not provide in-process multi-tenant isolation
or guarantees for adopter deployment topology, compliance attestations,
SBOM/signing, or advanced supply-chain controls. Adopters must supply those
controls and isolate separate tenants or trust domains in separate execution
environments. Experimental features do not receive stable API guarantees.
