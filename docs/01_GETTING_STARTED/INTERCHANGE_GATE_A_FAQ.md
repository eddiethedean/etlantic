# Interchange Gate A FAQ

> **Status: Available in ETLantic 0.18.0 (Gate A).** Public versioned tabular
> interchange for Polars ↔ Pandas boundaries.

## What shipped in Gate A?

A public, versioned tabular interchange contract (`etlantic.interchange/1`)
for Polars ↔ Pandas boundaries with descriptors and conformance coverage.
See [Capabilities](CAPABILITIES.md) and
`examples/interchange_polars_pandas.py`.

## What did *not* ship?

- Gate B / DataFusion-backed interchange (0.19+ experiment; non-blocking)
- A guarantee that legacy Arrow helpers are the Gate A contract

Best-effort Arrow-assisted conversion may still exist when PyArrow is
installed; it is **not** the Gate A interchange contract.

## Do I need to regenerate plans?

Yes, after upgrading into 0.18 if reviewed plans include interchange
boundaries or fingerprints that changed. See
[Migration 0.17 → 0.18](../11_DEVELOPMENT/MIGRATION_0_17_TO_0_18.md).

## How do I try it?

```bash
pip install 'etlantic==0.18.0' 'etlantic-polars==0.18.0' 'etlantic-pandas==0.18.0'
# from a checkout:
uv run python examples/interchange_polars_pandas.py
```

Docs guide: [Polars ↔ Pandas Interchange](../09_EXAMPLES/INTERCHANGE_POLARS_PANDAS.md).

## Failure modes

- Missing Polars or Pandas plugin
- Core/plugin minor skew
- Treating Arrow helpers as Gate A evidence in CI

## Related

- [Portable failure cookbook](PORTABLE_FAILURE_COOKBOOK.md)
- [Optional packages](../10_REFERENCE/OPTIONAL_PACKAGES.md)
