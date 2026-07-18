# Pandas Plugin

**Status: shipped in 0.5.0** as the compatibility dataframe backend
(`etlantic-pandas`).

The portable transformation compiler described below is planned for 0.14 and
is not part of the current 0.13 plugin.

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

## Portable compiler (planned 0.14)

The Pandas compiler will lower supported DTCS Transformation Plan expressions
to DataFrame and Series operations while declaring eager execution and ownership
copies honestly. Portable behavior cannot depend on a meaningful Pandas index.

It will claim individual capabilities or the published kernel/relational
profiles only after passing every required DTCS fixture. Eager execution does
not prevent conformance, but it must be declared in planning and ownership
metadata.

Where Pandas cannot preserve a required type, null, ordering, or lazy semantic,
planning fails instead of approximating the operation.

## Example

```bash
uv run --group dataframes python examples/dataframe_parity.py pandas
```
