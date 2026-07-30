# Documentation ownership map

> **Status: Available for maintainers.** Canonical owners for facts that must
> not drift across the corpus. Release numbers and maturity come from
> [`docs/release-facts.json`](../release-facts.json); `scripts/check_docs.py`
> loads that file.

| Fact | Owning page | Must not diverge |
|---|---|---|
| Current package version / minor | `docs/release-facts.json` (+ `src/etlantic/_version.py`) | ROADMAP header, CAPABILITIES, SUPPORT, homepage “current release”, INSTALLATION pins |
| Maturity (Beta) and support line | [`SUPPORT.md`](https://github.com/eddiethedean/etlantic/blob/main/SUPPORT.md) | docs SUPPORT pointer, KNOWN_ISSUES opening, SECURITY support table |
| What ships now | [`CAPABILITIES.md`](../01_GETTING_STARTED/CAPABILITIES.md) | Homepage limits copy, EVALUATOR, COMPARE |
| What's new / migration / exit gate | release-facts paths | Plan Index, Getting Started hub, ROADMAP evidence links |
| Immutable docs URL for a pin | [`DOCUMENTATION_VERSIONING.md`](../01_GETTING_STARTED/DOCUMENTATION_VERSIONING.md) | Root README + package READMEs (`/en/vX.Y.Z/`) |
| Supply-chain honesty (SHA-256 / SBOM) | [`RELEASE_ARTIFACT_VERIFICATION.md`](../01_GETTING_STARTED/RELEASE_ARTIFACT_VERIFICATION.md) | SECURITY, ENTERPRISE_EVALUATION, PRODUCTION_READINESS |
| Page status vocabulary | [`DOCUMENTATION.md`](DOCUMENTATION.md) | Product page frontmatter / status banners |
| Runnable example claims | [`DOCUMENTATION.md`](DOCUMENTATION.md) + `scripts/check_runnable_docs.py` | Tutorial “runnable” language |

When bumping a minor, update `release-facts.json` first, then run
`uv run python scripts/check_docs.py` and fix every failure before tagging.
