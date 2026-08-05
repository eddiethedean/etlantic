# Migration 0.44 → 0.45

> **Status: Available for ETLantic 0.45.0.** Upgrade notes for adopters moving
> from the published 0.44 developer-intelligence line to the published 0.45
> planner and optimization SDK line.

## Summary

| Area | Change |
|---|---|
| Package pin | `etlantic==0.45.0` (do not mix 0.44 and 0.45 minors) |
| Plugin floor | `etlantic>=0.45.0,<0.46` |
| New surface | `etlantic.optimization` (`etlantic.optimization/1`) |
| New profile fields | `optimization_pass_allowlist`, `optimization_policy` |
| New CLI | `etlantic plan optimize`; `plan explain --optimization` |
| New testing | `run_optimizer_conformance_suite` |
| Default behavior | Baseline plan unchanged unless policy applies accepted rewrites |

## Upgrade steps

1. Complete adoption on **0.44.x**.

2. Pin core and official plugins / Medallantic together:

   ```bash
   python -m pip install --upgrade 'etlantic==0.45.0'
   # plus matching plugins / medallantic at ==0.45.0
   ```

3. Optional: enable shadow optimization on a profile:

   ```python
   from etlantic import Profile
   from etlantic.optimization import builtin_passes

   profile = Profile(
       name="development",
       security_mode="development",
       optimization_policy="shadow",
       optimization_pass_allowlist={
           p.metadata.pass_id: p.metadata.version for p in builtin_passes()
       },
   )
   ```

4. Compare plans before applying:

   ```bash
   etlantic plan optimize module:MyPipeline --profile development
   ```

5. Production: set `optimization_pass_allowlist` explicitly; undeclared passes
   fail closed (`PMOPT140`). Keep `optimization_policy="off"` until ready.

## Compatibility notes

- Existing `etlantic.plan/1` fingerprints are unchanged for baseline plans.
- Optimized plans add `etlantic.optimization.*` metadata annotations and a new
  fingerprint when applied.
- IDE/LSP from 0.44 remain compatible; hosts may add the `optimize` IDE command.

## Related

- [What's New in 0.45](../01_GETTING_STARTED/WHATS_NEW_0_45.md)
- [Optimization Passes](../07_PLUGIN_SDK/OPTIMIZATION_PASSES.md)
- [ADR-021](adr/ADR-021-OPTIMIZER-PASS-PROTOCOL.md)
