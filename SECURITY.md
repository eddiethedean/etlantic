# Security Policy

Pipelantic 0.2 provides the typed modeling kernel and contract
interoperability. Security reports concerning the published package,
documentation, proposed APIs, repository automation, or later milestones are
welcome.

## Reporting a Vulnerability

Do not open a public issue for:

- credential exposure
- arbitrary code execution
- unsafe contract or configuration parsing
- path traversal
- server-side request forgery
- plugin supply-chain vulnerabilities
- injection vulnerabilities
- cross-tenant artifact or cache exposure

Until a private reporting address or GitHub private vulnerability reporting is
configured, contact the repository owner privately through an available
verified channel and include:

- affected component
- impact
- reproduction steps
- relevant configuration
- suggested mitigation, when known

Do not include production secrets, customer data, or regulated records.

## Supported Versions

| Version | Supported |
|---|---|
| 0.2.x | Best-effort while contract interoperability is in alpha |
| 0.1.x | Best-effort |
| earlier | Not supported |

A formal security patch policy will be published before 1.0.

## Security Model

The project threat model and production-readiness requirements are documented
in [docs/02_FOUNDATIONS/SECURITY.md](docs/02_FOUNDATIONS/SECURITY.md).

## Disclosure

The project intends to use coordinated disclosure:

1. Confirm receipt privately.
2. Validate and assess severity.
3. Develop and test a fix.
4. Prepare an advisory and upgrade guidance.
5. Release the fix before public technical details.

Response targets and a formal private reporting mechanism must be established
before Pipelantic is declared production-ready.
