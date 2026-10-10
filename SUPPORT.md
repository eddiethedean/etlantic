# Support

> **Version boundary:** ETLantic 0.57.0 is the current published Beta release and supported line.

> **Release candidate:** ETLantic 0.57.1 is being prepared; 0.57.0 remains the latest published release.


ETLantic **0.57.0** is the current published Beta release and **0.57.x**
support line. The 0.57 line targets documented
single-tenant pilots and retains **Supported** isolation
profiles (`isolated-deployment`, `dedicated-schema`). There is no hosted
multi-tenant SaaS. Community support has **no formal SLA** or guaranteed
response time.

## What we support

- Bug reports against the latest published minor line (`0.57.x`)
- Questions about documented Available APIs
- Security reports via [SECURITY.md](SECURITY.md) (private disclosure)

## Adopter-owned and unsupported areas

- Production incident response or on-call coverage
- Isolation topologies outside the Supported CP-GA profiles
- Compliance attestations (SOC2, GDPR certification, etc.)
- Advanced supply-chain programs beyond shipped SHA-256 digests, attestations,
  OIDC publish, documented package pins, and plugin allowlists (CycloneDX SBOM
  optional; verify the published release notes for the 0.57.x line)
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
