"""Small runnable smoke example for the qualified DuckDB 0.49 surface."""

from etlantic_duckdb import create_plugin

from etlantic.sql.protocol import RelationRef, SqlExecutionContext


def main() -> None:
    plugin = create_plugin()
    context = SqlExecutionContext(
        run_id="duckdb-example",
        pipeline_id="duckdb-example",
        plan_id="duckdb-example",
        step_name="load",
        engine="duckdb",
    )
    loaded = plugin.load_records(
        [{"id": 1, "name": "Ada"}, {"id": 2, "name": "Grace"}],
        target=RelationRef(name="people"),
        context=context,
    )
    if loaded.outcome.value != "committed":
        raise RuntimeError(loaded.diagnostics)
    fetched = plugin.fetch_records(
        RelationRef(name="people"), params={}, context=context
    )
    if fetched.records != [{"id": 1, "name": "Ada"}, {"id": 2, "name": "Grace"}]:
        raise AssertionError(fetched.records)
    plugin.cleanup_run(run_id=context.run_id)
    print("DuckDB portable example OK")


if __name__ == "__main__":
    main()
