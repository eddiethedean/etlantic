# Exit Gate 0.25 — Compatibility Burn-In (First Slice)

| Deliverable | Status |
|---|---|
| `etlantic.pipeline/1` 0.24→0.25 golden old↔new fixtures + CI gate | Done |
| Sibling codec matrix (plan, run_report, profile, capabilities, interchange) | Done |
| Wire schema ranges + unsupported downgrade docs | Done |
| Plugin SDK `/1` freeze decision (blockers published) | Done |
| 1.0 removal inventory | Done |
| WP5 fixture-blocking authoring polish | N/A — nested/clone/move fixtures green; residual deferred to 0.26 |
| Docs: What's New / Migration / this exit gate | Done |
| Core + plugins bumped to 0.25.0 | Done |

## Acceptance checklist

- [x] CI exercises documented **0.24 → 0.25** upgrade path for `etlantic.pipeline/1`
  (`tests/authoring/test_pipeline_upgrade_burn_in.py`,
  `scripts/check_pipeline_codec_burn_in.py`)
- [x] Additional versioned artifacts have the same fixture discipline
  (`tests/compatibility/test_codec_burn_in_matrix.py`)
- [x] Plugin SDK `/1` freeze decision recorded — **remaining blockers published**
  ([PROTOCOL_EVOLUTION.md](../07_PLUGIN_SDK/PROTOCOL_EVOLUTION.md)); not frozen
- [x] Published [1.0 removal candidates](REMOVAL_CANDIDATES_1_0.md); no new
  indefinite keep-forever aliases in 0.25
- [x] What's New / Migration 0.24→0.25 / this exit gate pass docs gates
- [x] No wire-schema reset; control plane and GUI remain out of scope

## WP5 note

Nested subpipeline golden fixtures round-trip; `clone` / `move` edits apply
without blocking burn-in evidence. Remaining nested-edit / parity polish that
does not block fixtures is deferred to **0.26 WP5**.

## Freeze blockers (carry to 0.26)

1. Document ≥1 external feedback cycle from a non-first-party plugin author
   (echo CI alone is insufficient per Exit Gate 0.22 freeze note).

## Residual / follow-ups (0.26+)

Owned by **[0.26 — Compatibility Burn-In (second slice)](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md#026--compatibility-burn-in-second-slice)**:

- Dual-minor proof (0.24→0.25 and 0.25→0.26)
- Freeze closure (clear blockers or re-scope)
- First-wave 1.0 removal execution
- Remaining authoring parity / nested-edit polish
