# etlantic-sparkforge (compatibility redirect)


Version **0.59.0** (lockstep with ETLantic core). The final compatibility
release is **0.62.0**; the adapter remains available through the 0.62 release
line and routine release builds stop in 0.63.0. The SparkForge adapter was renamed to
[**medallantic**](https://pypi.org/project/medallantic/) in ETLantic 0.27.

This wheel exists only so existing `pip install etlantic-sparkforge` workflows
receive a visible deprecation warning and re-exports from Medallantic. Migrate
before the 0.63 release; historic compatibility wheels remain available.

```bash
pip install medallantic
# or: pip install 'etlantic[medallantic]'
```

See [SparkForge migration](https://github.com/eddiethedean/etlantic/blob/main/packages/medallantic/docs/sparkforge-migration.md).

## Links

[Medallantic on PyPI](https://pypi.org/project/medallantic/) ·
[Migration guide](https://github.com/eddiethedean/etlantic/blob/main/packages/medallantic/docs/sparkforge-migration.md) ·
[Issues](https://github.com/eddiethedean/etlantic/issues)
