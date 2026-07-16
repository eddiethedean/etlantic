# Polars Plugin

**Status: shipped in 0.5.0** as the reference dataframe backend
(`pipelantic-polars`).

## Install

```bash
pip install pipelantic-polars
pip install 'pipelantic-polars[arrow]'  # optional
```

## Behavior

- Eager `DataFrame` execution is the baseline
- `LazyFrame` values are preserved across adjacent Polars steps
- Collection happens only at plan-declared boundaries (sink publication,
  cross-engine conversion, explicit collection points)
- Contract ↔ Polars dtype mapping with structured diagnostics for unsupported
  types
- Sync and async implementation callables are supported

## Example

See `examples/dataframe_parity.py` in the repository:

```bash
uv run --group dataframes python examples/dataframe_parity.py polars
```
