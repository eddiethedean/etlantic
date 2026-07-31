# Release fixtures — 0.37.0

Candidate-freeze and burn-in baselines for the **0.37 stable foundation**
release.

| Artifact | Purpose |
|---|---|
| `manifest.json` | `etlantic.release_baseline/1` — package digests filled at tag time (`status: candidate-pending` until wheels exist) |
| `compatibility_evidence.json` | Written by `scripts/check_isolated_codec_burn_in.py` (current-tree + optional `--isolated-wheels`) |

## Burn-in goldens

Current-reader goldens live under `tests/fixtures/burn_in/*/v0_37/` (copied from
`v0_36` — no wire-schema major reset in 0.37). Pipeline and sibling gates:

```bash
uv run python scripts/check_pipeline_codec_burn_in.py
uv run python scripts/check_codec_burn_in_matrix.py
```

If a codec change intentionally alters fingerprints, regenerate goldens and
update Migration / CHANGELOG (no silent field drops).

## Isolated-wheel regeneration

```bash
uv run python scripts/check_isolated_codec_burn_in.py
# Optional (network + published prior wheels):
uv run python scripts/check_isolated_codec_burn_in.py --isolated-wheels
```

Evidence defaults to this directory's `compatibility_evidence.json`.
