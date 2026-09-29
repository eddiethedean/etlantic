---
title: Release artifact verification for 0.55.0
status: published
current_minor: "0.55"
---

# Release artifact verification for 0.55.0

> **Status: ETLantic 0.55.0 is published.** The GitHub release contains the
> per-artifact manifest `release-artifacts.json` (48 package archives) and
> `sbom-warning.txt`; it does not contain a CycloneDX SBOM.

The release workflow is configured to build the core and first-party
distributions, publish a per-artifact SHA-256 manifest, and attest build
provenance. CycloneDX SBOM generation is optional. The published release
contains `sbom-warning.txt`, not a CycloneDX SBOM.

## Verify published assets

1. Open the [v0.55.0 GitHub Release](https://github.com/eddiethedean/etlantic/releases/tag/v0.55.0)
   and download a wheel and `release-artifacts.json`.
2. Compare the wheel's SHA-256 digest with its entry in the manifest, then
   verify build provenance for the downloaded wheel:

   ```bash
   gh attestation verify path/to/etlantic-0.55.0-*.whl \
     --owner eddiethedean \
     --repo etlantic
   ```

3. The release contains `sbom-warning.txt`; no CycloneDX SBOM asset was
   published.
4. Prefer exact pins such as `etlantic==0.55.0` and matching first-party
   plugins in lockfiles.

The release asset list and per-artifact digests are recorded in the GitHub
release manifest.
