# etlantic-datafusion (Experimental)

Gate B experimental DataFusion plugin stub for ETLantic 0.37.

**Not recommended for production.** Does not replace Polars as the reference
dataframe engine. Advertises no graduated dataframe/Arrow/lazy capabilities
until conformance, differentials, Gate A Arrow boundaries, and a measured
advantage are complete.

## Install

```bash
pip install etlantic-datafusion
```

The package currently exposes a capability-gated plugin stub. Use
[`etlantic-polars`](https://pypi.org/project/etlantic-polars/) for supported
dataframe execution.

## Links

[Capabilities](https://etlantic.readthedocs.io/en/v0.37.0/01_GETTING_STARTED/CAPABILITIES/) ·
[Source](https://github.com/eddiethedean/etlantic/tree/main/packages/etlantic-datafusion) ·
[Issues](https://github.com/eddiethedean/etlantic/issues)
