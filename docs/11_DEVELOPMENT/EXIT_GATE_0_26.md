# Exit Gate 0.26 — Compatibility Burn-In (Second Slice)

| Deliverable | Status |
|---|---|
| Dual-minor burn-in (`v0_24/` + `v0_25/` fixtures) | Done |
| Sibling codec matrix complete (plan, run_report, profile, capabilities, interchange) | Done |
| Authoring-catalog N/A documented in wire ranges | Done |
| Plugin SDK `/1` freeze re-scoped to 0.27 | Done |
| First-wave root alias removals (protocol/exceptions/storage/runtime/interchange) | Done |
| WP5 authoring parity | N/A — no residual blocking gaps found in audit |
| Docs: What's New / Migration / this exit gate | Done |
| Core + plugins bumped to 0.26.0 | Done |

## Acceptance checklist

- [x] CI exercises **0.24 → 0.25** and **0.25 → 0.26** upgrade paths for
  `etlantic.pipeline/1` (`tests/authoring/test_pipeline_upgrade_burn_in.py`,
  `scripts/check_pipeline_codec_burn_in.py`)
- [x] Sibling artifacts have dual-minor fixture discipline
  (`tests/compatibility/test_codec_burn_in_matrix.py`,
  `scripts/check_codec_burn_in_matrix.py`)
- [x] Plugin SDK `/1` freeze decision — **re-scoped to 0.27** with owners
  ([PROTOCOL_EVOLUTION.md](../07_PLUGIN_SDK/PROTOCOL_EVOLUTION.md))
  — owned by [Exit gate 0.27](EXIT_GATE_0_27.md)
- [x] First-wave [1.0 removal candidates](REMOVAL_CANDIDATES_1_0.md) executed
- [x] What's New / Migration 0.25→0.26 / this exit gate pass docs gates
- [x] No wire-schema reset; control plane and GUI remain out of scope

## WP5 note

Nested subpipeline golden fixtures remain green from 0.25. Audit found no
additional class↔functional or nested-edit gaps blocking burn-in evidence.

## Freeze blockers (carried to 0.27)

1. Document ≥1 external feedback cycle from a non-first-party plugin author
   (echo CI alone is insufficient per Exit Gate 0.22 freeze note).

## Residual / follow-ons (0.27)

- Protocol `/1` freeze closure (clear blocker or re-scope again with owners) —
  owned by [Exit gate 0.27](EXIT_GATE_0_27.md)
- Remaining demoted root aliases (`REM-ROOT-DEMOTED` lower-traffic symbols)
- `REM-RELIABILITY-ROOT` and later 1.0 inventory items
