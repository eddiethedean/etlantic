# What's New in ETLantic 0.14

> **Status: Historical release notes for ETLantic 0.14.0.** Current line is
> **0.18.0** — see [What's new in 0.18](WHATS_NEW_0_18.md).

ETLantic 0.14 completes the first three-engine portable transformation
baseline. A kernel or `portable-relational/1` transformation can now compile
for Polars, PySpark, or Pandas when it stays within the selected compiler's
advertised capabilities.

## Pandas portable compilation

`etlantic-pandas` now provides a portable transform compiler through the
`etlantic.transform_compilers` entry point. It claims the kernel and
`portable-relational/1` profiles with eager, index-neutral execution.

This means Pandas plans that previously needed a native
`@implementation("pandas")` under
`portable_transform_policy="require"` can compile from one portable definition
when every action, function, type, and semantic mode is supported.

Pandas remains an eager backend. Unsupported lazy behavior or capabilities
fail during planning instead of silently changing semantics.

## Public compiler conformance

The portable compiler suite is now public:

```python
from etlantic.testing import run_portable_transform_conformance_suite

run_portable_transform_conformance_suite(my_compiler)
```

The suite selects mandatory fixtures from the compiler's advertised
capabilities. A compiler that claims a profile, action, or function must pass
the corresponding cases.

## CI coverage

The 0.14 release gates include:

- Pandas compiler suites;
- public conformance runs for Polars, Pandas, and PySpark;
- three-engine differential tests;
- property tests for capability matching, null-aware boolean semantics, and
  compile fingerprint stability.

This coverage verifies the advertised intersection. It does not imply support
for profiles outside kernel and `portable-relational/1`.

## Upgrade notes

Pin core and official plugins to the same release:

```bash
pip install --upgrade \
  'etlantic==0.14.0' \
  'etlantic-polars==0.14.0' \
  'etlantic-pandas==0.14.0' \
  'etlantic-pyspark==0.14.0'
```

- Extras also pin official packages to `==0.14.0`.
- Re-plan Pandas pipelines that previously fell back to native implementations;
  supported portable plans can now select `portable_compiled`.
- Third-party compiler maintainers should run
  `run_portable_transform_conformance_suite` for every advertised claim.
- Keep native implementations for unsupported profiles and for explicit
  `portable_transform_policy="native"` use.

Review the complete [0.14 changelog](https://github.com/eddiethedean/etlantic/blob/main/CHANGELOG.md#0140---2026-07-18)
before upgrading.

## Continue

- [Capabilities and Limitations](CAPABILITIES.md)
- [Migration 0.13 → 0.14](../11_DEVELOPMENT/MIGRATION_0_13_TO_0_14.md)
- [Portable Transformations](../04_TRANSFORMATIONS/PORTABLE_TRANSFORMATIONS.md)
- [Testing Plugins](../07_PLUGIN_SDK/TESTING_PLUGINS.md)
