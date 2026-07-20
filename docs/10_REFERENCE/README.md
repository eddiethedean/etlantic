# Reference

This section separates ETLantic **0.21** shipped behavior from proposed 1.0
interfaces.

## Shipped

- [Command-Line Interface](CLI.md)
- [Python API](API_REFERENCE.md)
- [Runtime configuration](RUNTIME_CONFIGURATION.md) (env vars and Profile-in-Python)
- [Compatibility Matrix](COMPATIBILITY.md)
- [Portable Compiler Matrix](PORTABLE_COMPILER_MATRIX.md)
- [Known Limitations](KNOWN_ISSUES.md)
- [Diagnostics](DIAGNOSTICS.md)
- [Exceptions](EXCEPTIONS.md)
- DTCS 3.0 Transformation Plan / Rich Portable Analytics models through
  `dtcs>=0.13`; ETLantic `@Transformation.portable` authoring (0.11+) and
  Polars / PySpark graduated Wave 1/2 compilers plus Pandas / SQL baseline
  relational compilers via
  [Portable Transform Compiler](../07_PLUGIN_SDK/PORTABLE_TRANSFORM_COMPILER.md)
  and
  [Testing Plugins](../07_PLUGIN_SDK/TESTING_PLUGINS.md)

## Future design / proposed 1.0

- [Configuration](CONFIGURATION.md) (`etlantic.toml` fantasy)
- [Environment Variables](ENVIRONMENT_VARIABLES.md) (proposed names beyond shipped)
- 0.17 continuation families (`portable-relational-extended/1`,
  `portable-temporal-iana/1`, `portable-nondeterministic/1`,
  `portable-window/2`) — see the
  [Portable Compiler Matrix](PORTABLE_COMPILER_MATRIX.md)

See [Documentation Status](../02_FOUNDATIONS/DOCUMENTATION_STATUS.md) for the
stability vocabulary used throughout the project.
