# Reference

This section separates ETLantic **0.13** shipped behavior from proposed 1.0
interfaces.

## Shipped

- [Command-Line Interface](CLI.md)
- [Python API](API_REFERENCE.md)
- [Runtime configuration](RUNTIME_CONFIGURATION.md) (env vars and Profile-in-Python)
- [Compatibility Matrix](COMPATIBILITY.md)
- [Known Limitations](KNOWN_ISSUES.md)
- [Diagnostics](DIAGNOSTICS.md)
- [Exceptions](EXCEPTIONS.md)
- DTCS 3.0 Transformation Plan / Rich Portable Analytics models through
  `dtcs>=0.13`; ETLantic `@Transformation.portable` authoring (0.11+) and
  Polars **kernel** portable compiler (0.12) via
  [Portable Transform Compiler](../07_PLUGIN_SDK/PORTABLE_TRANSFORM_COMPILER.md)

## Future design / proposed 1.0

- [Configuration](CONFIGURATION.md) (`etlantic.toml` fantasy)
- [Environment Variables](ENVIRONMENT_VARIABLES.md) (proposed names beyond shipped)
- Portable compilers for **PySpark / relational / Pandas / SQL** planned across
  0.13–0.15 — see
  [Portable Transform Compiler](../07_PLUGIN_SDK/PORTABLE_TRANSFORM_COMPILER.md)
  for the shipped protocol and Polars claim. Authoring docs live under
  [Portable Transformations](../04_TRANSFORMATIONS/PORTABLE_TRANSFORMATIONS.md).

See [Documentation Status](../02_FOUNDATIONS/DOCUMENTATION_STATUS.md) for the
stability vocabulary used throughout the project.
