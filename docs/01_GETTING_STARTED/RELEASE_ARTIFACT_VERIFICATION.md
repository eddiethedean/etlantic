---
title: Release artifact verification for 0.55.0
status: candidate
current_minor: "0.55"
---

# Release artifact verification for 0.55.0

> **Status: 0.55.0 Beta release candidate; no 0.55.0 artifacts are published
> yet.** Verify the assets only after the release workflow completes.

The release workflow is configured to build the core and first-party
distributions, publish a per-artifact SHA-256 manifest, and attest build
provenance. CycloneDX SBOM generation is optional. The actual release assets
determine which SBOM statement applies; this candidate document does not
predict that result.

## After publication

1. Open the [v0.55.0 GitHub Release](https://github.com/eddiethedean/etlantic/releases/tag/v0.55.0)
   and download the wheel, `release-artifacts.json`, and its checksum.
2. Verify the checksum against the published manifest and verify build
   provenance for the downloaded wheel:

   ```bash
   gh attestation verify path/to/etlantic-0.55.0-*.whl \
     --owner eddiethedean \
     --repo etlantic
   ```

3. Confirm whether that release contains `etlantic-environment.cdx.json` or
   `sbom-warning.txt`; record only the asset that was actually published.
4. Prefer exact pins such as `etlantic==0.55.0` and matching first-party
   plugins in lockfiles.

Update this page with the actual asset names and verification result after the
release workflow has completed.
