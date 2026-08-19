# Support

ETLantic **0.48.0** is a **Beta** release suitable for documented single-tenant
pilots. You can embed an HTTP control plane with **Supported** isolation
profiles (`isolated-deployment`, `dedicated-schema`). There is no hosted
multi-tenant SaaS. Community support has **no formal SLA** or guaranteed
response time.

## What we support

- Bug reports against the **current published minor** (`0.48.x`)
- Questions about documented Available APIs
- Security reports via [SECURITY.md](SECURITY.md) (private disclosure)

## Adopter-owned and unsupported areas

- Production incident response or on-call coverage
- Isolation topologies outside the Supported CP-GA profiles
- Compliance attestations (SOC2, GDPR certification, etc.)
- Advanced supply-chain programs beyond shipped SHA-256 digests, attestations,
  OIDC publish, documented package pins, and plugin allowlists (CycloneDX SBOM
  optional; failed for v0.35.0 — verify the current release notes for 0.48.x)
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
