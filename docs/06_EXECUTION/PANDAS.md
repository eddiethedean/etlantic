# Pandas Plugin

**Status: shipped in 0.5.0** as the compatibility dataframe backend
(`etlantic-pandas`). Portable transform compiler shipped in **0.14**.

## Install

```bash
pip install etlantic-pandas
pip install 'etlantic-pandas[arrow]'  # optional
```

## Behavior

- Eager `DataFrame` execution only
- Planning fails when a pipeline requires unsupported lazy or zero-copy
  behavior
- Copy-on-write / deep-copy ownership rules isolate branches and retries
- Object-dtype ambiguity produces structured warnings
- Arrow interchange is used when PyArrow is installed; otherwise a documented
  fallback copies values and records the conversion

## Portable compiler (shipped 0.14)

The Pandas compiler lowers `dtcs.transform-plan/2` kernel and
`portable-relational/1` IR to DataFrame / Series operations. It declares
`eager=True` and `lazy=False`, ignores Pandas indexes as semantic input, and
registers the `etlantic.transform_compilers` entry point `pandas`.

Claimed modes match the 0.13 Polars/PySpark matrix (join `collisionPolicy`
`fail` only). Unsupported modes fail during `analyze()` with action paths.
Third-party and reference compilers must pass
`etlantic.testing.run_portable_transform_conformance_suite`.

## Example

See [Pandas Tutorial](PANDAS_TUTORIAL.md) and
[Portable Transformation](../09_EXAMPLES/PORTABLE_TRANSFORMATION.md).
