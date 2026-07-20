# Contract-First Workflow

> **Status: Available in ETLantic 0.21.0.** Uses shipped
> `write_contracts` / `load_bundle` APIs (no separate companion script).

Generate ODCS/DTCS/DPCS from a code-first pipeline, then reload contracts with
the shipped interchange helpers. Longer design studies under
[Contract First](CONTRACT_FIRST.md) are **not** current API guides.

## Generate contracts

```python
from pathlib import Path

from etlantic.interchange import write_contracts

# CustomerPipeline is your Pipeline subclass
bundle = write_contracts(CustomerPipeline, Path("contracts"))
print(sorted(bundle.paths))
```

Or via CLI:

```bash
etlantic generate path/to/pipeline.py:CustomerPipeline -o contracts/
```

## Load a bundle

```python
from etlantic.interchange import load_bundle

bundle = load_bundle("contracts")
print(bundle.pipeline_id)
print(sorted(bundle.data_contracts))
```

## Rebuild typed objects (when artifacts are complete)

```python
from etlantic import Pipeline, Transformation

# When you have DTCS / DPCS documents:
# transform_cls = Transformation.from_dtcs(dtcs_document)
# pipeline_cls = Pipeline.from_dpcs(dpcs_document)
```

Validate signatures against the
[API reference](../10_REFERENCE/API_REFERENCE.md) for your installed version—
`from_dtcs` / `from_dpcs` accept the document shapes produced by
`write_contracts` / `etlantic generate`.

## Next

- [Generation](../03_DATA_CONTRACTS/GENERATION.md) (check page status)
- [DPCS](../05_PIPELINES/DPCS.md)
- [CLI generate](../10_REFERENCE/CLI.md)
