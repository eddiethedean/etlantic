# Support

ETLantic **0.55.0** is the Beta release candidate; **0.54.0** remains the
latest published Beta release until the 0.55.0 tag is published. The 0.55 line
targets documented single-tenant pilots and retains **Supported** isolation
profiles (`isolated-deployment`, `dedicated-schema`). There is no hosted
multi-tenant SaaS. Community support has **no formal SLA** or guaranteed
response time.

## What we support

- Bug reports against the latest published minor line (`0.54.x`) until 0.55.0
  is published; then use the `0.55.x` line
- Questions about documented Available APIs
- Security reports via [SECURITY.md](SECURITY.md) (private disclosure)

## Adopter-owned and unsupported areas

- Production incident response or on-call coverage
- Isolation topologies outside the Supported CP-GA profiles
- Compliance attestations (SOC2, GDPR certification, etc.)
- Advanced supply-chain programs beyond shipped SHA-256 digests, attestations,
  OIDC publish, documented package pins, and plugin allowlists (CycloneDX SBOM
  optional; verify the published release notes for the 0.55.x line)
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
