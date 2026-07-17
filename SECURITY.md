# Security Policy

ETLantic 0.11.0 is an alpha release. Security reports concerning the
published package, contract loading, planning, local runtime, storage
bindings, secret handling, dataframe, SQL, and PySpark plugins,
documentation, or repository automation are welcome.

## Supported Versions

| Version | Support |
|---|---|
| 0.11.x | Current alpha line; best-effort security fixes |
| 0.10.x | Critical fixes only when practical |
| 0.9.x | Critical fixes only when practical |
| 0.8.x and earlier | Not supported |

Upgrade to the latest patch release before reporting an issue.

## Reporting a Vulnerability

Do not open a public issue for a suspected vulnerability.

Use GitHub private vulnerability reporting when it is enabled for the
repository. If it is unavailable, contact the repository owner privately
through the verified contact listed in the package metadata and request a
secure reporting channel before sending sensitive details.

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

## Disclosure

The project follows coordinated disclosure: acknowledge the report, assess
impact, prepare and test a fix, publish an upgrade, and then disclose technical
details at an appropriate time.

Formal response-time guarantees are not available during the alpha series.
