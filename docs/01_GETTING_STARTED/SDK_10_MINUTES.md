# SDK 10-minute tutorial

> **Status: Available in ETLantic 0.44.0.** Secondary path — complete the CLI
> [Quickstart](QUICKSTART.md) (Ada/Grace in `data/out.json`) first. This page
> is for SDK muscle memory after that green path. No clone required.

Use the curated root (`import etlantic as etl`) for a tiny in-process pipeline.

## Install

Same install as [Installation](INSTALLATION.md):

```bash
python -m pip install 'etlantic==0.44.0'
```

## Author, validate, plan, run

```python
import etlantic as etl


class Row(etl.Data):
    id: int
    name: str


class Identity(etl.Transformation):
    rows: etl.Input[Row]
    result: etl.Output[Row]


@Identity.implementation("local")
def identity_local(rows: list[Row]) -> list[Row]:
    return list(rows)


class Demo(etl.Pipeline):
    raw: etl.Extract[Row] = etl.Extract(asset="rows")
    step = Identity.step(rows=raw)
    out: etl.Load[Row] = etl.Load(input=step.result, asset="out")


profile = etl.Profile(name="sdk-demo", assets={"rows": "memory", "out": "memory"})
runtime = etl.PipelineRuntime()
runtime.memory.seed(
    "rows",
    [Row(id=1, name="Ada"), Row(id=2, name="Grace")],
)

Demo.validate(profile=profile).raise_for_errors()
Demo.plan(profile=profile)
run = Demo.run(profile=profile, runtime=runtime)
assert run.status.value == "succeeded"
print(runtime.memory.get("out"))
```

## Notes

- Curated symbols match `_CURATED` — see [API reference](../10_REFERENCE/API_REFERENCE.md).
- **Primary path remains CLI** `init` → validate → run. Use this page only after
  first file-backed success.
- Next: [First Pipeline](FIRST_PIPELINE.md) (if you skipped it),
  [Engine selection](ENGINE_SELECTION.md).
