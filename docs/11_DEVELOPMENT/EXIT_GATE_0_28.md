# Exit Gate 0.28 — Burn-In (Fourth Slice) and Plugin Freeze

> **Status: Planned** (not shipped). Medallantic M0 rename and first PyPI
> publish landed in **0.27.0**; 0.28 closes M0 and opens the quadruple-minor
> window.

| Deliverable | Status |
|---|---|
| Quadruple-minor burn-in (`v0_27/` fixtures; 0.26→0.27→0.28) | Planned |
| Plugin SDK `/1` freeze closure or dated re-scope | Planned |
| Third-wave `REM-ROOT-DEMOTED` removals (sql, profile, lifecycle, …) | Planned |
| Medallantic M0 closeout (redirect decision, facade release category) | Planned |
| Wire matrix maintenance for `v0_27/` | Planned |
| Docs: What's New / Migration / this exit gate | Planned |
| Core + plugins bumped to 0.28.0 | Planned |

## Acceptance checklist

- [ ] CI exercises **0.26 → 0.27 → 0.28** upgrade paths for
  `etlantic.pipeline/1` and sibling burn-in artifacts (`v0_27/` goldens +
  extended check scripts)
- [ ] Plugin SDK `/1` freeze decision — **frozen** or **re-scoped to 0.29+**
  with owners ([PROTOCOL_EVOLUTION.md](../07_PLUGIN_SDK/PROTOCOL_EVOLUTION.md))
- [ ] Third-wave demoted root removals executed with migration notes
  ([REMOVAL_CANDIDATES_1_0.md](REMOVAL_CANDIDATES_1_0.md))
- [ ] `medallantic` M0 closeout: `etlantic-sparkforge` redirect decision
  documented; facade package category in release process
- [ ] Wire schema ranges document the quadruple-minor window
- [ ] What's New / Migration 0.27→0.28 / this exit gate pass docs gates
- [ ] No wire-schema reset; native medallion authoring (M1) remains **0.29**

## Carried from 0.27

1. Document ≥1 external feedback cycle from a non-first-party plugin author
   (echo CI alone is insufficient per Exit Gate 0.22).

## Residual / follow-ons (0.29+)

- Native `MedallionPipeline` authoring and facade conformance kit (**M1 / 0.29**)
- Remaining demoted root aliases toward 1.0
- `REM-DATACONTRACTMODEL`, experimental surface graduation

## See also

- [ROADMAP § 0.28](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md#028--burn-in-fourth-slice-plugin-freeze-and-medallantic-m0-closeout)
- [Exit gate 0.27](EXIT_GATE_0_27.md)
- [Medallantic roadmap](https://github.com/eddiethedean/etlantic/blob/main/packages/medallantic/ROADMAP.md)
