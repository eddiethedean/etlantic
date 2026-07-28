# Exit Gate 0.27 — Compatibility Burn-In (Third Slice)

| Deliverable | Status |
|---|---|
| Triple-minor burn-in (`v0_26/` fixtures; 0.25→0.26→0.27) | Done |
| Protocol `/1` freeze re-scoped to 0.28+ | Done |
| Second-wave root removals (`REM-RELIABILITY-ROOT` + schema_drift + registry) | Done |
| Wire matrix maintenance for `v0_26/` | Done |
| WP5 trust/docs residuals | N/A — no release-blocking residuals beyond docs/version bump |
| Docs: What's New / Migration / this exit gate | Done |
| Core + plugins bumped to 0.27.0 | Done |

## Acceptance checklist

- [x] CI exercises **0.25 → 0.26 → 0.27** upgrade paths for
  `etlantic.pipeline/1` and sibling burn-in artifacts (`v0_26/` goldens +
  extended check scripts)
- [x] Plugin SDK `/1` freeze decision — **re-scoped to 0.28+** with owners
  ([PROTOCOL_EVOLUTION.md](../07_PLUGIN_SDK/PROTOCOL_EVOLUTION.md))
- [x] `REM-RELIABILITY-ROOT` and schema_drift + registry demoted wave executed with
  migration notes ([REMOVAL_CANDIDATES_1_0.md](REMOVAL_CANDIDATES_1_0.md))
- [x] Wire schema ranges document the triple-minor window
- [x] What's New / Migration 0.26→0.27 / this exit gate pass docs gates
- [x] No wire-schema reset; control plane and GUI remain out of scope

## Freeze blockers (carried to 0.28+)

1. Document ≥1 external feedback cycle from a non-first-party plugin author
   (echo CI alone is insufficient per Exit Gate 0.22 freeze note).

## Residual / follow-ons (0.28+)

- Protocol `/1` freeze closure — owned by [Exit gate 0.28](EXIT_GATE_0_28.md)
- Remaining demoted root aliases (`sql`, `profile`, lifecycle, …) — third wave in 0.28
- Later 1.0 inventory items (`REM-DATACONTRACTMODEL`, experimental surfaces)

## See also

- [ROADMAP § 0.27](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md#027--compatibility-burn-in-third-slice)
- [What's New 0.27](../01_GETTING_STARTED/WHATS_NEW_0_27.md)
- [Migration 0.26 → 0.27](MIGRATION_0_26_TO_0_27.md)
- [Exit gate 0.26](EXIT_GATE_0_26.md)
- [Exit gate 0.28](EXIT_GATE_0_28.md) (planned)
