---
title: Release artifact verification for 0.56.0
status: candidate
current_minor: "0.56"
---

# Release artifact verification for 0.56.0

> **Status: 0.56.0 is a qualification candidate and has not been published.**
> The supported published line remains 0.55.x.

## Verify candidate wheels

The phase qualification builds all lockstep candidate wheels and records each
archive digest in the [0.56 wheel manifest](../11_DEVELOPMENT/evidence/phase_0_56/WHEEL_MANIFEST.json).
The package compatibility report records the isolated installation, runtime
resolution, compatibility checks, and schema snapshots.

Rebuild the candidate wheel set from the repository root with:

```bash
uv build --all-packages --wheel --out-dir /tmp/etlantic-phase056-candidate-wheels --clear
uv run python scripts/qualify_phase056_packages.py \
  --repo-root . \
  --wheel-dir /tmp/etlantic-phase056-candidate-wheels \
  --output docs/11_DEVELOPMENT/evidence/phase_0_56/PACKAGE_COMPATIBILITY_0_56.json
```

Before any future publication, the release workflow must produce
`release-artifacts.json`, a per-artifact SHA-256 manifest, and provenance
attestations for the published `0.56.0` assets. The workflow may also emit
`sbom-warning.txt` if SBOM generation is unavailable.
This candidate record does not imply those release assets exist.
