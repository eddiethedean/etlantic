# What's New in ETLantic 0.27

> **Status: Planned for ETLantic 0.27** (not shipped). Compatibility Burn-In
> (third slice): prove **0.25 → 0.26 → 0.27** without a wire-schema reset;
> close or re-scope Plugin SDK `/1` freeze; second-wave root removals.

## Planned highlights

- Triple-minor burn-in: golden **`v0_26/`** fixtures alongside existing
  `v0_25/` (and prior) trees for pipeline, plan, run_report, profile,
  capabilities, and interchange
- CI gates extended for the triple-minor window
- Plugin SDK `/1` freeze closure (external feedback) **or** explicit re-scope
  with owners
- Second-wave root alias removals: `REM-RELIABILITY-ROOT` plus a bounded
  demoted-alias wave
- [Migration 0.26 → 0.27](../11_DEVELOPMENT/MIGRATION_0_26_TO_0_27.md) and
  [Exit gate 0.27](../11_DEVELOPMENT/EXIT_GATE_0_27.md)

## Not in 0.27

- Complete 1.0 removal list (later burn-in / 0.99)
- Production FastAPI control plane / GUI / new engines / DataFusion graduation

## See also

- Current release notes: [What's New in 0.26](WHATS_NEW_0_26.md)
- [Roadmap summary](../11_DEVELOPMENT/ROADMAP_SUMMARY.md)
