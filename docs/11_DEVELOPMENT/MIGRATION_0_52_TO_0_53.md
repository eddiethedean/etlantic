# Migration 0.52 → 0.53

Upgrade core and every installed first-party plugin together. The new lockstep
dependency range is `etlantic>=0.53.0,<0.54`.

```bash
python -m pip install 'etlantic==0.53.0' 'etlantic-polars==0.53.0' 'etlantic-pandas==0.53.0'
```

Explicit profiles remain the default, and existing `/1` bytes, runtime APIs and
correct engine override behavior remain compatible. No database or persisted
state migration is required. Keep production plugin, optimization-pass,
schema-registry and resource-provider allowlists enabled.

Adaptive execution is Experimental and requires a fresh executable plan whose
topology, policies and exact versions match a packaged qualified support row.
Historical 0.51/0.52 planning-only `/2` documents remain readable and verifiable
but reject execution. Replan the source pipeline; never relabel, mutate or
downgrade a stored `/2` plan to bypass admission.

Adaptive `RunRequest.implementation_overrides` values are target IDs. Request
overrides apply before planning and cannot widen eligibility or select native
bodies. An opted-in planning-time explicit fallback independently resolves its
engine descriptors; LocalScheduler does not reinterpret its target IDs as
engine names. Ordinary explicit requests continue to use engine names.

The qualified backend versions are Polars 1.42.1, Pandas 2.3.3 and PyArrow
25.0.0. General installation ranges are not qualification claims. See
[evidence](evidence/adaptive_0_53/README.md) for the finite support boundary.

Rollback by repinning the complete 0.52.1 package set and using explicit
profiles. An executable 0.53 `/2` plan is not an executable 0.52 document;
replan from source when changing the execution version or strategy.
