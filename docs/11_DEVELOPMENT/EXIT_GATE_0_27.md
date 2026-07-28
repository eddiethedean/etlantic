# Exit Gate 0.27 — Compatibility Burn-In (Third Slice)

| Deliverable | Status |
|---|---|
| Triple-minor burn-in (`v0_26/` fixtures; 0.25→0.26→0.27) | Not started |
| Protocol `/1` freeze closure (external feedback or re-scope) | Not started |
| Second-wave root removals (`REM-RELIABILITY-ROOT` + demoted wave) | Not started |
| Wire matrix maintenance for `v0_26/` | Not started |
| WP5 trust/docs residuals | Not started |
| Docs: What's New / Migration / this exit gate | Planned stubs |
| Core + plugins bumped to 0.27.0 | Not started |

## Acceptance checklist

- [ ] CI exercises **0.25 → 0.26 → 0.27** upgrade paths for
  `etlantic.pipeline/1` and sibling burn-in artifacts (`v0_26/` goldens +
  extended check scripts)
- [ ] Plugin SDK `/1` freeze decision — frozen **or** blockers cleared/rescheduled
  with owners ([PROTOCOL_EVOLUTION.md](../07_PLUGIN_SDK/PROTOCOL_EVOLUTION.md))
- [ ] `REM-RELIABILITY-ROOT` and chosen `REM-ROOT-DEMOTED` wave executed with
  migration notes ([REMOVAL_CANDIDATES_1_0.md](REMOVAL_CANDIDATES_1_0.md))
- [ ] Wire schema ranges document the triple-minor window
- [ ] What's New / Migration 0.26→0.27 / this exit gate pass docs gates
- [ ] No wire-schema reset; control plane and GUI remain out of scope

## Freeze blockers (from 0.26)

1. Document ≥1 external feedback cycle from a non-first-party plugin author
   (echo CI alone is insufficient per Exit Gate 0.22 freeze note).

## Residual / follow-ons (0.28+)

- Remaining demoted root aliases after the 0.27 wave
- Later 1.0 inventory items (`REM-DATACONTRACTMODEL`, experimental surfaces)
- Continued consecutive-minor burn-in toward 0.99 RC

## See also

- [ROADMAP § 0.27](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md#027--compatibility-burn-in-third-slice)
- [What's New 0.27](../01_GETTING_STARTED/WHATS_NEW_0_27.md) (planned)
- [Migration 0.26 → 0.27](MIGRATION_0_26_TO_0_27.md) (planned)
- [Exit gate 0.26](EXIT_GATE_0_26.md)
