# Current Capabilities and Limitations

Pipelantic 0.6.0 is an alpha release. This page is the shortest answer to
"What can I use today?"

## Available in 0.6

| Capability | Status |
|---|---|
| Typed data, transformation, and pipeline models | Available |
| Structural and semantic validation | Available |
| ODCS, DTCS, and DPCS generation and loading | Available |
| Profiles and deterministic, secret-free pipeline plans | Available |
| Local synchronous and asynchronous execution | Available |
| Python transformation implementations | Available |
| Memory, callable, JSON, CSV, and no-write storage | Available |
| Run reports, structured logging, and local debugging | Available |
| Runtime secret references and env/file providers | Available |
| Dataframe execution protocol (`pipelantic.dataframe/1`) | Available |
| Polars plugin (eager + lazy preservation) | Available (`pipelantic-polars`) |
| Pandas plugin (eager compatibility) | Available (`pipelantic-pandas`) |
| Optional Arrow interchange | Available when PyArrow is installed |
| SQL execution protocol (`pipelantic.sql/1`) | Available |
| SQL plugin (PostgreSQL reference) | Available (`pipelantic-sql`) |
| Mermaid diagrams (`Pipeline.to_mermaid`) | Available |

## Not included in 0.6

| Capability | Status |
|---|---|
| PySpark or streaming execution | Future design (0.7) |
| Airflow or other orchestrator compilation | Future design (0.8) |
| Public third-party Plugin SDK polish | Continues in 0.9 |
| Graphviz and generated HTML pipeline documentation | Future design |
| Stable 1.0 compatibility guarantees | Not yet |

## Install matrix

```bash
pip install pipelantic                 # core only — no engines
pip install pipelantic-polars          # Polars reference plugin
pip install pipelantic-pandas          # Pandas compatibility plugin
pip install pipelantic-sql             # PostgreSQL SQL reference plugin
pip install 'pipelantic-polars[arrow]' # optional PyArrow
```

Core never imports Polars, Pandas, PyArrow, NumPy, or database drivers.

## Next Step

Continue with [Quickstart](QUICKSTART.md), or read the
[Evaluator brief](EVALUATOR.md) if you are assessing the project for adoption.
