# pipelantic-polars

Polars reference dataframe plugin for [Pipelantic](https://github.com/eddiethedean/pipelantic).

```bash
pip install pipelantic-polars
# optional Arrow interchange
pip install 'pipelantic-polars[arrow]'
```

Supports eager `DataFrame` execution and `LazyFrame` preservation until an
explicit collection boundary declared in the `PipelinePlan`.
