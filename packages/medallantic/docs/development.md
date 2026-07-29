# Development

## Workspace setup

From the ETLantic repository root:

```bash
uv sync --locked --group medallantic
```

Run the adapter suite:

```bash
uv run pytest -q tests/medallantic -m medallantic
```

Run focused lint:

```bash
uv run ruff check \
  packages/medallantic/src/medallantic \
  tests/medallantic
```

Build the distribution:

```bash
uv build --package medallantic
```

## Test layers

1. IR tests run without SparkForge, SQLAlchemy, PySpark, or Delta.
2. Semantic conformance uses one logical fixture across supported engines.
3. Legacy differential tests compare graph order, validation, writes, and
   normalized reports.
4. Backend integration tests cover physical SQL, PySpark, and Delta behavior.

Unit tests alone do not establish backend parity.

## Contribution rules

- Keep medallion vocabulary out of `src/etlantic`.
- Prefer public ETLantic SDK imports.
- Add a core capability only when it is domain-neutral.
- Fail closed for unsupported engines, rules, writes, or Delta operations.
- Never serialize secrets, source rows, live backend objects, or callables.
- Preserve diagnostic and serialized-field compatibility or add a migration.
- Add conformance evidence for every new parity claim.
- Keep planned APIs labeled as planned until their acceptance tests pass.

## Useful files

- `src/medallantic/ir.py` — secret-free migration IR
- `src/medallantic/adapt.py` — ETLantic graph/profile mapping
- `src/medallantic/compat.py` — write, retry, and Delta compatibility
- `src/medallantic/runtime_map.py` — run intent and selection mapping
- `src/medallantic/reports.py` — normalized report conversion
- `tests/medallantic/` — current parity fixtures
- `ROADMAP.md` — full Spark and SQL parity plan
