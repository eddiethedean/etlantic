# etlantic-sparkforge (compatibility redirect)

**Final release.** The SparkForge adapter was renamed to
[**medallantic**](https://pypi.org/project/medallantic/) in ETLantic 0.27.

This wheel exists only so existing `pip install etlantic-sparkforge` workflows
receive a deprecation warning and re-exports from Medallantic.

```bash
pip install medallantic
# or: pip install 'etlantic[medallantic]'
```

See [SparkForge migration](../medallantic/docs/sparkforge-migration.md).
