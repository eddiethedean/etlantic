# Pandas Plugin

**Status: shipped in 0.5.0** as the compatibility dataframe backend
(`pipelantic-pandas`).

## Install

```bash
pip install pipelantic-pandas
pip install 'pipelantic-pandas[arrow]'  # optional
```

## Behavior

- Eager `DataFrame` execution only
- Planning fails when a pipeline requires unsupported lazy or zero-copy
  behavior
- Copy-on-write / deep-copy ownership rules isolate branches and retries
- Object-dtype ambiguity produces structured warnings
- Arrow interchange is used when PyArrow is installed; otherwise a documented
  fallback copies values and records the conversion

## Example

```bash
uv run --group dataframes python examples/dataframe_parity.py pandas
```
