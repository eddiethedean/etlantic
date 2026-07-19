# Support

ETLantic **0.18.0** is **stable** for documented single-tenant reference
deployments (not unrestricted enterprise production). Community support has
**no formal SLA** or guaranteed response time.

## What we support

- Bug reports against the **current published minor** (`0.18.x`)
- Questions about documented Available APIs
- Security reports via [SECURITY.md](SECURITY.md) (private disclosure)

## Adopter-owned and unsupported areas

- Production incident response or on-call coverage
- Multi-tenant isolation and deployment topology
- Compliance attestations (SOC2, GDPR certification, etc.)
- SBOM/signing and advanced supply-chain controls beyond documented package
  pins and plugin allowlists
- Guarantees for Experimental APIs (for example Structured Streaming)
- Guarantees for Future design / Design Proposal pages

## Before opening an issue

1. Confirm `etlantic --version` and Python version
2. Reproduce with a **minimal** public example (no credentials, no production
   data, no private plans)
3. Prefer SARIF/JSON validate output over screenshots of secrets

Read the maintainer [support policy](docs/11_DEVELOPMENT/SUPPORT.md).
Never paste credentials into GitHub.
