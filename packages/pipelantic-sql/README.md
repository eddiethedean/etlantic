# pipelantic-sql

PostgreSQL reference SQL execution plugin for [Pipelantic](https://github.com/eddiethedean/pipelantic).

```bash
pip install pipelantic-sql
export PIPELANTIC_SQL_URL=postgresql+psycopg://user:pass@localhost:5432/pipelantic
```

Uses SQLAlchemy Core. Driver dependencies stay out of `pipelantic` core.
