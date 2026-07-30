# Reference

This section separates ETLantic **0.34** shipped behavior from proposed 0.x
interfaces.

## Shipped

- [Python API](https://etlantic.readthedocs.io/en/latest/10_REFERENCE/API_REFERENCE/) — hub + [Authoring](https://etlantic.readthedocs.io/en/latest/10_REFERENCE/API_AUTHORING/) /
  [Plan and runtime](https://etlantic.readthedocs.io/en/latest/10_REFERENCE/API_PLAN_RUNTIME/) / [Quality](https://etlantic.readthedocs.io/en/latest/10_REFERENCE/API_QUALITY/) /
  [Protocols](https://etlantic.readthedocs.io/en/latest/10_REFERENCE/API_PROTOCOLS/)
- [Command-Line Interface](https://etlantic.readthedocs.io/en/latest/10_REFERENCE/CLI/)
- [Cheatsheet](https://etlantic.readthedocs.io/en/latest/10_REFERENCE/CHEATSHEET/)
- [Programmatic authoring](https://etlantic.readthedocs.io/en/latest/05_PIPELINES/PROGRAMMATIC_AUTHORING/)
  (`PipelineDefinition`, `etlantic.pipeline/1`, builders, service)
- [Runtime configuration](https://etlantic.readthedocs.io/en/latest/10_REFERENCE/RUNTIME_CONFIGURATION/) (Profile, optional `etlantic.toml`, env vars)
- [Configuration today](https://etlantic.readthedocs.io/en/latest/10_REFERENCE/CONFIGURATION_TODAY/) (shipped profile + project toml)
- [Secrets decision tree](https://etlantic.readthedocs.io/en/latest/10_REFERENCE/SECRETS_DECISION/) (SecretRef / env mapping)
- [Compatibility Matrix](https://etlantic.readthedocs.io/en/latest/10_REFERENCE/COMPATIBILITY/)
- [Portable Compiler Matrix](https://etlantic.readthedocs.io/en/latest/10_REFERENCE/PORTABLE_COMPILER_MATRIX/)
- [Optional Packages](https://etlantic.readthedocs.io/en/latest/10_REFERENCE/OPTIONAL_PACKAGES/) (core-first API; plugin READMEs on GitHub)
- [Known Limitations](https://etlantic.readthedocs.io/en/latest/10_REFERENCE/KNOWN_ISSUES/)
- [Diagnostics](https://etlantic.readthedocs.io/en/latest/10_REFERENCE/DIAGNOSTICS/)
- [Exceptions](https://etlantic.readthedocs.io/en/latest/10_REFERENCE/EXCEPTIONS/)
- [DTCS](https://etlantic.readthedocs.io/en/latest/04_TRANSFORMATIONS/DTCS/) 3.0 Transformation Plan / Rich Portable Analytics models through
  `dtcs>=0.13`; ETLantic `@Transformation.portable` authoring (0.11+) and
  Polars / PySpark graduated Wave 1/2 compilers plus Pandas / SQL baseline
  relational compilers via
  [Portable Transform Compiler](https://etlantic.readthedocs.io/en/latest/07_PLUGIN_SDK/PORTABLE_TRANSFORM_COMPILER/)
  and
  [Testing Plugins](https://etlantic.readthedocs.io/en/latest/07_PLUGIN_SDK/TESTING_PLUGINS/)

## Future design / planned 0.x

- [Configuration](https://etlantic.readthedocs.io/en/latest/10_REFERENCE/CONFIGURATION/) (**proposed** 0.38 — do not implement for 0.34)
- [Environment Variables](https://etlantic.readthedocs.io/en/latest/10_REFERENCE/ENVIRONMENT_VARIABLES/) (**proposed** names beyond shipped)
- 0.17 continuation families (`portable-relational-extended/1`,
  `portable-temporal-iana/1`, `portable-nondeterministic/1`,
  `portable-window/2`) — see the
  [Portable Compiler Matrix](https://etlantic.readthedocs.io/en/latest/10_REFERENCE/PORTABLE_COMPILER_MATRIX/)

See [Documentation Status](https://etlantic.readthedocs.io/en/latest/02_FOUNDATIONS/DOCUMENTATION_STATUS/) for the
stability vocabulary used throughout the project.
