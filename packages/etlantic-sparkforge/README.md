# etlantic-sparkforge (compatibility redirect)

**Final release.** The SparkForge adapter was renamed to
[**medallantic**](https://pypi.org/project/medallantic/) in ETLantic 0.27.

This wheel exists only so existing `pip install etlantic-sparkforge` workflows
receive a deprecation warning and re-exports from Medallantic.

```bash
pip install medallantic
# or: pip install 'etlantic[medallantic]'
```

See [SparkForge migration](https://github.com/eddiethedean/etlantic/blob/main/packages/medallantic/docs/sparkforge-migration.md).

## Links

[Medallantic on PyPI](https://pypi.org/project/medallantic/) ·
[Migration guide](https://github.com/eddiethedean/etlantic/blob/main/packages/medallantic/docs/sparkforge-migration.md) ·
[Issues](https://github.com/eddiethedean/etlantic/issues)
