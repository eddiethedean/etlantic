# etlantic-datafusion

Version **0.50.1** (provisional implementation; lockstep with ETLantic core).

This package provides a capability-gated DataFusion dataframe plugin and a
portable DTCS transform compiler. Native dependencies are installed with the
package and are never imported by ETLantic core.

## Install

```bash
pip install etlantic-datafusion
```

The compiler supports the portable kernel/relational action set, scalar and
aggregate functions, Arrow interchange, lazy execution, schema inspection,
and deterministic support/evidence reports. Unsupported extensions fail during
analysis before execution.

Use `@Transformation.portable` with
`portable_transform_policy="require"`. This recommended engine-neutral path is
eligible for adaptive execution; engine-specific bodies are not.

## Links

[Capabilities](https://etlantic.readthedocs.io/en/v0.50.1/01_GETTING_STARTED/CAPABILITIES/) ·
[Source](https://github.com/eddiethedean/etlantic/tree/main/packages/etlantic-datafusion) ·
[Issues](https://github.com/eddiethedean/etlantic/issues)
