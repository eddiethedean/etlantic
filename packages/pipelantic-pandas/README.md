# pipelantic-pandas

Pandas compatibility dataframe plugin for [Pipelantic](https://github.com/eddiethedean/pipelantic).

```bash
pip install pipelantic-pandas
pip install 'pipelantic-pandas[arrow]'  # optional Arrow interchange
```

Eager `DataFrame` execution only. Planning fails closed when a pipeline
requires unsupported lazy or zero-copy behavior.
