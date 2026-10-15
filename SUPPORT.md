# Support

> **Version boundary:** ETLantic core 0.60.0 is an unpublished Beta candidate; 0.59.x remains the published support line. The independent `etlantic-rsconnect` 0.60.0 preview is published, with live Connect and production qualification deferred.


ETLantic core **0.60.0** is a Beta candidate, and **0.59.x** remains the current
published core support line. The `etlantic-rsconnect` 0.60.0 preview is published
as a separate package without live Connect or production support qualification.
Core targets documented single-tenant pilots and
retains **Supported** isolation
profiles (`isolated-deployment`, `dedicated-schema`). There is no hosted
multi-tenant SaaS. Community support has **no formal SLA** or guaranteed
response time.

The 0.60 shared managed-execution contracts and 0.61 AWS adapter remain
unreleased or unqualified for production use while their external campaigns are deferred.

## What we support

- Bug reports against the latest published minor line (`0.59.x`)
- Questions about documented Available APIs
- Security reports via [SECURITY.md](SECURITY.md) (private disclosure)

## Adopter-owned and unsupported areas

- Production incident response or on-call coverage
- Isolation topologies outside the Supported CP-GA profiles
- Compliance attestations (SOC2, GDPR certification, etc.)
- Advanced supply-chain programs beyond shipped SHA-256 digests, attestations,
  OIDC publish, documented package pins, and plugin allowlists (CycloneDX SBOM
  optional; verify the published release notes for the 0.59.x line)
- Guarantees for Experimental APIs (for example Structured Streaming, shared-service)
- Guarantees for Future design / Design Proposal pages
- Formal enterprise SLA or unbounded scale claims

## Before opening an issue

1. Confirm `etlantic --version` and Python version
2. Reproduce with a **minimal** public example (no credentials, no production
   data, no private plans)
3. Prefer SARIF/JSON validate output over screenshots of secrets

Read the maintainer [support policy](docs/11_DEVELOPMENT/SUPPORT.md).
Never paste credentials into GitHub.
