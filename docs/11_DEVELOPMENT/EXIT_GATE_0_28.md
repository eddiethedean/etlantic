# Exit Gate 0.28 — Burn-In (Fourth Slice) and Plugin Freeze

> **Status: Shipped in ETLantic 0.28.0.** Medallantic M0 rename and first PyPI
> publish landed in **0.28.0**; 0.28 closes M0 and opens the quadruple-minor
> window.

| Deliverable | Status |
|---|---|
| Quadruple-minor burn-in (`v0_27/` fixtures; 0.26→0.27→0.28) | Done |
| Plugin SDK `/1` freeze closure | Done — frozen in 0.28.0 |
| Third-wave `REM-ROOT-DEMOTED` removals (sql, profile, lifecycle, …) | Done |
| Medallantic M0 closeout (redirect decision, facade release category) | Done |
| Wire matrix maintenance for `v0_27/` | Done |
| Docs: What's New / Migration / this exit gate | Done |
| Core + plugins bumped to 0.28.0 | Done |

## Acceptance checklist

- [x] CI exercises **0.26 → 0.27 → 0.28** upgrade paths for
  `etlantic.pipeline/1` and sibling burn-in artifacts (`v0_27/` goldens +
  extended check scripts)
- [x] Plugin SDK `/1` freeze decision — **frozen in 0.28.0**
  ([PROTOCOL_EVOLUTION.md](../07_PLUGIN_SDK/PROTOCOL_EVOLUTION.md))
- [x] Third-wave demoted root removals executed with migration notes
  ([REMOVAL_CANDIDATES_0_38.md](REMOVAL_CANDIDATES_0_38.md))
- [x] `medallantic` M0 closeout: `etlantic-sparkforge` redirect wheel ships;
  facade package category documented
- [x] Wire schema ranges document the quadruple-minor window
- [x] What's New / Migration 0.27→0.28 / this exit gate pass docs gates
- [x] No wire-schema reset; native medallion authoring (M1) **shipped in 0.29.0**

## Residual / follow-ons (0.30+)

- Portable quality / rule DSL (**M2 / 0.30**)
- Remaining demoted root aliases toward 0.38
- `REM-DATACONTRACTMODEL`, experimental surface graduation

## See also

- [ROADMAP § 0.28](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md#028--burn-in-fourth-slice-plugin-freeze-and-medallantic-m0-closeout)
- [Exit gate 0.27](EXIT_GATE_0_27.md)
- [Medallantic roadmap](https://github.com/eddiethedean/etlantic/blob/main/packages/medallantic/ROADMAP.md)
