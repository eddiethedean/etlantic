---
title: Release artifact verification for 0.57.0
status: available
current_minor: "0.57"
---

# Release artifact verification for 0.57.0

> **Status: 0.57.0 is published.** Release assets include all 25 package
> distributions, `release-artifacts.json`, and `sbom-warning.txt`.

## Verify published artifacts

The [GitHub release](https://github.com/eddiethedean/etlantic/releases/tag/v0.57.0)
contains the published distributions and `release-artifacts.json`, which records
the release artifact inventory and SHA-256 digests. The workflow also published
provenance attestations. `sbom-warning.txt` records that an SBOM was unavailable
for this release. The phase qualification's [wheel manifest](../11_DEVELOPMENT/evidence/phase_0_56/WHEEL_MANIFEST.json)
and package compatibility report are build-time qualification evidence.

Rebuild the qualification wheel set from the repository root with:

```bash
uv build --all-packages --wheel --out-dir /tmp/etlantic-phase056-candidate-wheels --clear
uv run python scripts/qualify_phase056_packages.py \
  --repo-root . \
  --wheel-dir /tmp/etlantic-phase056-candidate-wheels \
  --output docs/11_DEVELOPMENT/evidence/phase_0_56/PACKAGE_COMPATIBILITY_0_56.json
```

Use the GitHub release asset page to download the manifest and verify a
downloaded artifact against its recorded digest. For future releases, confirm
the release workflow publishes the same inventory and provenance evidence.
