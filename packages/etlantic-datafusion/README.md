# etlantic-datafusion

Version **0.49.0** (lockstep with ETLantic core).

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

## Links

[Capabilities](https://etlantic.readthedocs.io/en/v0.49.0/01_GETTING_STARTED/CAPABILITIES/) ·
[Source](https://github.com/eddiethedean/etlantic/tree/main/packages/etlantic-datafusion) ·
[Issues](https://github.com/eddiethedean/etlantic/issues)
