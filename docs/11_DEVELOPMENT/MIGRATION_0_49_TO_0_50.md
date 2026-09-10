# Migration 0.49 → 0.50

> **Status: Applies to the published ETLantic 0.50.0 Beta release.**

## Repin the lockstep packages

Install core and every first-party plugin on the same minor line. Official
plugin metadata requires `etlantic>=0.50.0,<0.51`.

```bash
python -m pip install 'etlantic==0.50.0' 'etlantic-polars==0.50.0'
```

Do not mix 0.49 and 0.50 packages. Production profiles must retain explicit
plugin allowlists.

## Replan portable pipelines

The `etlantic.plan/1` reader can inspect stored 0.49 plans, but runtime
preflight rejects stale or missing requirement-level compiler evidence before
I/O. Validate and plan each portable target again with the 0.50 package set.

```bash
etlantic validate pipeline.py:Pipeline --format json
etlantic plan pipeline.py:Pipeline --format json
```

Third-party transform compilers must emit one bounded support finding for every
applicable normalized requirement. Missing evidence becomes `unknown` and
cannot satisfy a required obligation. Rerun the public `etlantic.testing`
conformance suite before restoring a baseline claim.

## Portable and native behavior

The shared guarantee is the frozen `etlantic.portable-baseline/1` contract.
Advanced profiles remain engine-specific. Native implementation bodies remain
explicit escape hatches; a rejected portable implementation never falls back
to one silently.

## Rollback

Re-pin the complete 0.49.x core/plugin set, restore plans produced by that set,
and remove any 0.50-only baseline claim. Never reuse a 0.50 support fingerprint
with a 0.49 compiler.

The canonical campaign details remain in the
[evidence migration record](evidence/portable_0_50/MIGRATION_0_49_TO_0_50.md).
