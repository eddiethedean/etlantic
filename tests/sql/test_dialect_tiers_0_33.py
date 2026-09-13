"""0.33 dialect tiers, merge compile, and model DDL helpers."""

from __future__ import annotations

import os

import pytest

pytest.importorskip("sqlalchemy")

from etlantic.sql.expression import col
from etlantic.sql.protocol import (
    AliasedExpr,
    CallExpr,
    CteDef,
    LiteralExpr,
    RelationRef,
    SqlExecutionContext,
    SqlQuery,
    SqlWrite,
    WriteIntentKind,
)
from etlantic_sql.compiler import SqlCompiler
from etlantic_sql.dialect_tiers import detect_dialect_info
from etlantic_sql.plugin import PostgresSqlPlugin

pytestmark = pytest.mark.sql


def test_dialect_tier_a_sqlite_and_postgresql() -> None:
    assert detect_dialect_info("sqlite+pysqlite:///:memory:").tier == "A"
    assert detect_dialect_info("postgresql+psycopg://localhost/db").name == "postgresql"
    assert detect_dialect_info("postgresql+psycopg://localhost/db").supports_merge


def test_dialect_tier_b_mysql_gated() -> None:
    info = detect_dialect_info("mysql+pymysql://localhost/db")
    assert info.name == "mysql"
    assert info.tier == "B"
    assert not info.supports_merge


def test_sqlite_plugin_refuses_merge_compile() -> None:
    plugin = PostgresSqlPlugin(url="sqlite+pysqlite:///:memory:")
    assert not plugin.capabilities().supports("sql_merge")
    assert plugin.capabilities().supports("sql_cte")
    ctx = SqlExecutionContext(
        run_id="r", pipeline_id="p", plan_id="plan", step_name="m"
    )
    write = SqlWrite(
        intent=WriteIntentKind.MERGE,
        target=RelationRef(name="t"),
        source=RelationRef(name="s"),
        merge_keys=("id",),
    )
    with pytest.raises(ValueError, match="PostgreSQL"):
        plugin.compile_write(write, context=ctx)


def test_postgresql_merge_compile_on_conflict() -> None:
    compiler = SqlCompiler(dialect="postgresql", supports_merge=True)
    ctx = SqlExecutionContext(
        run_id="r", pipeline_id="p", plan_id="plan", step_name="m"
    )
    write = SqlWrite(
        intent=WriteIntentKind.MERGE,
        target=RelationRef(name="customers"),
        source=SqlQuery(
            source=RelationRef(name="staging"),
            columns=(col("id"), col("name")),
        ),
        merge_keys=("id",),
        metadata={"update_columns": ["name"]},
    )
    compiled = compiler.compile_write(write, context=ctx)
    assert "ON CONFLICT" in compiled.text
    assert "EXCLUDED" in compiled.text
    assert "DO UPDATE SET" in compiled.text


def test_postgresql_sigma_context_does_not_use_locale_case_mapping() -> None:
    """Final-sigma context classification must be locale-independent."""
    compiler = SqlCompiler(dialect="postgresql", supports_merge=True)
    compiled = compiler.compile_query(
        SqlQuery(
            source=RelationRef(name="customers"),
            columns=(
                AliasedExpr(
                    CallExpr("dtcs:lower", (col("name"),)),
                    "lower_name",
                ),
            ),
        ),
        context=SqlExecutionContext(
            run_id="r", pipeline_id="p", plan_id="plan", step_name="lower"
        ),
    )

    assert "RIGHT(" in compiled.text
    assert " !~ '" in compiled.text
    assert "UPPER(RIGHT(" not in compiled.text
    assert "LOWER(RIGHT(" not in compiled.text
    assert "TRANSLATE(" in compiled.text
    assert "ASCII(etlantic_chars.ch)" not in compiled.text


def test_postgresql_sigma_mapping_is_stable_under_c_collation() -> None:
    """Unicode sigma mapping must not depend on PostgreSQL's C locale."""
    if not os.environ.get("ETLANTIC_SQL_URL", "").startswith("postgresql"):
        pytest.skip("PostgreSQL collation verification requires ETLANTIC_SQL_URL")
    from sqlalchemy import create_engine, text

    compiler = SqlCompiler(dialect="postgresql", supports_merge=True)
    compiled = compiler.compile_query(
        SqlQuery(
            source=RelationRef(name="sigma_c_033"),
            columns=(
                AliasedExpr(
                    CallExpr("dtcs:lower", (col("name"),)),
                    "lower_name",
                ),
            ),
        ),
        context=SqlExecutionContext(
            run_id="r", pipeline_id="p", plan_id="plan", step_name="lower"
        ),
    )
    engine = create_engine(os.environ["ETLANTIC_SQL_URL"])
    try:
        with engine.begin() as connection:
            connection.execute(
                text('CREATE TEMP TABLE sigma_c_033 (name TEXT COLLATE "C")')
            )
            connection.execute(
                text("INSERT INTO sigma_c_033 VALUES ('A-Σ'), ('AΣ-B'), ('A-𞤀')")
            )
            rows = connection.execute(
                text(compiled.text), compiled.metadata["_bound_params"]
            ).all()
    finally:
        engine.dispose()
    assert rows == [("a-\u03c3",), ("a\u03c2-b",), ("a-𞤢",)]


@pytest.mark.parametrize("mode", ["lower", "upper"])
def test_postgresql_casing_preserves_input_collation(mode: str) -> None:
    """Context classification must not force the result to C collation."""
    if not os.environ.get("ETLANTIC_SQL_URL", "").startswith("postgresql"):
        pytest.skip("PostgreSQL collation verification requires ETLANTIC_SQL_URL")
    from sqlalchemy import create_engine, text

    compiler = SqlCompiler(dialect="postgresql", supports_merge=True)
    compiled = compiler.compile_query(
        SqlQuery(
            source=RelationRef(name="sigma_collation_033"),
            columns=(
                AliasedExpr(
                    CallExpr(f"dtcs:{mode}", (col("name"),)),
                    "lower_name",
                ),
            ),
        ),
        context=SqlExecutionContext(
            run_id="r", pipeline_id="p", plan_id="plan", step_name="lower"
        ),
    )
    engine = create_engine(os.environ["ETLANTIC_SQL_URL"])
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TEMP TABLE sigma_collation_033 "
                    '(name TEXT COLLATE "en-US-x-icu")'
                )
            )
            connection.execute(text("INSERT INTO sigma_collation_033 VALUES ('Ä')"))
            rows = connection.execute(
                text(
                    "SELECT pg_collation_for(lower_name), lower_name < 'z' "
                    f"FROM ({compiled.text}) AS lowered"
                ),
                compiled.metadata["_bound_params"],
            ).all()
    finally:
        engine.dispose()
    assert rows == [('"en-US-x-icu"', True)]


def _nested_casing_query(modes: tuple[str, ...]) -> SqlQuery:
    expression = col("name")
    for mode in modes:
        expression = CallExpr(f"dtcs:{mode}", (expression,))
    return SqlQuery(
        source=RelationRef(name="nested_casing_033"),
        columns=(col("id"), AliasedExpr(expression, "value")),
    )


def test_postgresql_nested_casing_sql_grows_linearly() -> None:
    """Casing binds its operand once, including the null-propagation check."""
    compiler = SqlCompiler(dialect="postgresql", supports_merge=True)
    context = SqlExecutionContext(
        run_id="r", pipeline_id="p", plan_id="plan", step_name="nested"
    )
    for mode in ("upper", "lower"):
        for depth in (1, 2, 4, 8):
            compiled = compiler.compile_query(
                _nested_casing_query((mode,) * depth), context=context
            )
            assert compiled.text.count('"name"') == 1
            assert len(compiled.text.encode("utf-8")) < 50_000 * depth


@pytest.mark.parametrize(
    "modes",
    [
        ("upper",) * 4,
        ("lower",) * 4,
        ("upper", "lower", "upper", "lower"),
    ],
)
def test_postgresql_nested_casing_execution(modes: tuple[str, ...]) -> None:
    """Nested operand scopes preserve nulls, empty strings, and Unicode context."""
    if not os.environ.get("ETLANTIC_SQL_URL", "").startswith("postgresql"):
        pytest.skip("PostgreSQL execution requires ETLANTIC_SQL_URL")
    from sqlalchemy import create_engine, text

    compiler = SqlCompiler(dialect="postgresql", supports_merge=True)
    compiled = compiler.compile_query(
        _nested_casing_query(modes),
        context=SqlExecutionContext(
            run_id="r", pipeline_id="p", plan_id="plan", step_name="nested"
        ),
    )
    values = [None, "", "ASCII", "ßİ", "AΣ:B", "AΣ\u0301"]
    engine = create_engine(os.environ["ETLANTIC_SQL_URL"])
    try:
        with engine.begin() as connection:
            connection.execute(
                text("CREATE TEMP TABLE nested_casing_033 (id INTEGER, name TEXT)")
            )
            connection.execute(
                text("INSERT INTO nested_casing_033 VALUES (:id, :name)"),
                [{"id": index, "name": value} for index, value in enumerate(values)],
            )
            rows = connection.execute(
                text(compiled.text + ' ORDER BY "id"'),
                compiled.metadata["_bound_params"],
            ).all()
    finally:
        engine.dispose()
    expected = []
    for index, value in enumerate(values):
        for mode in modes:
            value = None if value is None else getattr(value, mode)()
        expected.append((index, value))
    assert rows == expected


def test_sql_compiler_evidence_fingerprints_unicode_database() -> None:
    """Unicode-dependent SQL lowering must identify its Unicode data version."""
    from etlantic_sql.transform_compiler import create_transform_compiler
    from etlantic_sql.unicode_data import UNICODE_DATA_FINGERPRINT, UNICODE_DATA_VERSION

    compiler = create_transform_compiler()
    assert compiler.info.environment["unicode"] == UNICODE_DATA_VERSION
    assert compiler.info.environment["unicode_fingerprint"] == UNICODE_DATA_FINGERPRINT


@pytest.mark.parametrize("mode", ["lower", "upper"])
@pytest.mark.parametrize("aggregate", ["count_all", "count", "sum", "max"])
def test_postgresql_casing_rejects_unscoped_aggregate(
    mode: str, aggregate: str
) -> None:
    """A field-free aggregate must not be moved into the operand SELECT."""
    args = () if aggregate == "count_all" else (LiteralExpr(1),)
    expression = CallExpr(f"dtcs:{mode}", (CallExpr(f"dtcs:{aggregate}", args),))
    compiler = SqlCompiler(dialect="postgresql", supports_merge=True)
    with pytest.raises(ValueError, match=r"aggregate.*separate step"):
        compiler.compile_query(
            SqlQuery(
                source=RelationRef(name="items"),
                columns=(AliasedExpr(expression, "value"),),
            ),
            context=SqlExecutionContext(
                run_id="r", pipeline_id="p", plan_id="plan", step_name="case"
            ),
        )


@pytest.mark.parametrize("mode", ["lower", "upper"])
@pytest.mark.parametrize("aggregate", ["count_all", "count", "sum", "max"])
def test_portable_postgresql_casing_rejects_unscoped_aggregate(
    mode: str, aggregate: str
) -> None:
    from etlantic.transform.compiler import (
        TransformCompileContext,
        TransformPlanningContext,
    )
    from etlantic_sql.transform_compiler import SqlTransformCompiler

    args = (
        []
        if aggregate == "count_all"
        else [{"kind": "literal", "value": {"type": "integer", "value": 1}}]
    )
    expression = {
        "kind": "call",
        "callee": f"dtcs:{mode}",
        "args": [{"kind": "call", "callee": f"dtcs:{aggregate}", "args": args}],
    }
    definition = {
        "planIdentity": "dtcs.transform-plan/2",
        "inputs": {"t": {}},
        "actions": [
            {
                "id": "a",
                "kind": {
                    "id": "a",
                    "action": "dtcs:aggregate",
                    "target": "t",
                    "parameters": {
                        "groupBy": [],
                        "aggregates": [{"name": "value", "expression": expression}],
                    },
                },
            }
        ],
        "outputs": {"result": {"id": "result"}},
        "requirements": {
            "dependencies": [{"from": "a", "to": "result", "reason": "lineage"}]
        },
    }
    compiler = SqlTransformCompiler(dialect="postgresql")
    context = TransformPlanningContext("p", "s", "profile", "sql")
    report = compiler.analyze(definition, context=context)
    assert not report.supported
    assert any(
        finding.requirement == "mode:casing_aggregate_scope"
        for finding in report.findings
    )
    with pytest.raises(ValueError, match=r"aggregate.*separate step"):
        compiler.compile(
            definition,
            context=TransformCompileContext("p", "plan", "s", "profile", "sql"),
        )

    # Ordinary aggregates and aggregates with outer field references retain
    # their original scope and must not be rejected by this guard.
    compiler = SqlTransformCompiler(dialect="sqlite")
    assert compiler.analyze(definition, context=context).supported
    expression["args"][0]["callee"] = "dtcs:max"
    expression["args"][0]["args"] = [
        {"kind": "fieldRef", "scope": "field", "target": "name"}
    ]
    compiler = SqlTransformCompiler(dialect="postgresql")
    assert compiler.analyze(definition, context=context).supported


@pytest.mark.parametrize("mode", ["lower", "upper"])
@pytest.mark.parametrize("row_count", [0, 3])
def test_postgresql_casing_preserves_supported_aggregate_scopes(
    mode: str, row_count: int
) -> None:
    """Counts in a separate step and directly cased column aggregates work."""
    if not os.environ.get("ETLANTIC_SQL_URL", "").startswith("postgresql"):
        pytest.skip("PostgreSQL execution requires ETLANTIC_SQL_URL")
    from sqlalchemy import create_engine, text

    context = SqlExecutionContext(
        run_id="r", pipeline_id="p", plan_id="plan", step_name="scope"
    )
    source = RelationRef(name="aggregate_scope_033")
    counted = SqlQuery(
        source=source,
        columns=(AliasedExpr(CallExpr("dtcs:count_all"), "total"),),
    )
    queries = (
        SqlQuery(
            source=RelationRef(name="counted"),
            ctes=(CteDef(name="counted", query=counted),),
            columns=(CallExpr(f"dtcs:{mode}", (col("total"),)),),
        ),
        SqlQuery(
            source=source,
            columns=(
                CallExpr(f"dtcs:{mode}", (CallExpr("dtcs:max", (col("name"),)),)),
            ),
        ),
    )
    engine = create_engine(os.environ["ETLANTIC_SQL_URL"])
    try:
        with engine.begin() as connection:
            connection.execute(
                text("CREATE TEMP TABLE aggregate_scope_033 (name TEXT)")
            )
            if row_count:
                connection.execute(
                    text("INSERT INTO aggregate_scope_033 VALUES (:name)"),
                    [{"name": "AbC"}] * row_count,
                )
            for query, expected in zip(
                queries,
                [str(row_count), getattr("AbC", mode)() if row_count else None],
                strict=True,
            ):
                compiled = SqlCompiler(
                    dialect="postgresql", supports_merge=True
                ).compile_query(query, context=context)
                rows = connection.execute(
                    text(compiled.text), compiled.metadata["_bound_params"]
                ).all()
                assert rows == [(expected,)]
    finally:
        engine.dispose()


def test_sql_compiler_identity_honors_database_url(monkeypatch) -> None:
    """Compiler evidence must match the runtime URL fallback."""
    monkeypatch.delenv("ETLANTIC_SQL_URL", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://postgres:postgres@127.0.0.1/db"
    )
    from etlantic_sql.transform_compiler import create_transform_compiler

    compiler = create_transform_compiler()
    assert compiler.info.environment["dialect"] == "postgresql"


@pytest.mark.parametrize("host_unicode", ["15.0.0", "15.1.0"])
@pytest.mark.parametrize("dialect", ["sqlite", "postgresql"])
@pytest.mark.parametrize("callee", ["dtcs:lower", "dtcs:upper"])
def test_sql_portable_casing_accepts_newer_host_unicode(
    monkeypatch, host_unicode: str, dialect: str, callee: str
) -> None:
    """Pinned SQL casing is independent of the host Unicode database."""
    import unicodedata

    from etlantic.transform.compiler import TransformPlanningContext
    from etlantic_sql.transform_compiler import SqlTransformCompiler

    monkeypatch.setattr(unicodedata, "unidata_version", host_unicode)
    compiler = SqlTransformCompiler(dialect=dialect)
    definition = {
        "planIdentity": "dtcs.transform-plan/2",
        "actions": [
            {
                "kind": {
                    "action": "dtcs:project",
                    "parameters": {
                        "fields": [
                            {
                                "name": "value",
                                "expression": {
                                    "kind": "call",
                                    "callee": callee,
                                    "args": [
                                        {
                                            "kind": "fieldRef",
                                            "scope": "field",
                                            "target": "text",
                                        }
                                    ],
                                },
                            }
                        ]
                    },
                }
            }
        ],
    }
    report = compiler.analyze(
        definition,
        context=TransformPlanningContext("p", "s", "profile", "sql"),
    )
    assert report.supported, report.findings

    literal_definition = {
        **definition,
        "actions": [
            {
                "kind": {
                    "action": "dtcs:project",
                    "parameters": {
                        "fields": [
                            {
                                "name": "value",
                                "expression": {
                                    "kind": "literal",
                                    "value": {
                                        "type": "string",
                                        "value": "dtcs:lower",
                                    },
                                },
                            }
                        ]
                    },
                }
            }
        ],
    }
    literal_report = compiler.analyze(
        literal_definition,
        context=TransformPlanningContext("p", "s", "profile", "sql"),
    )
    assert literal_report.supported, literal_report.findings


def test_model_create_and_pk_validation_sqlite() -> None:
    pytest.importorskip("sqlmodel")
    from sqlmodel import Field, SQLModel

    class Customer(SQLModel, table=True):
        __tablename__ = "customers_033"
        id: int = Field(primary_key=True)
        name: str

    plugin = PostgresSqlPlugin(url="sqlite+pysqlite:///:memory:")
    created = plugin.create_table_from_model(Customer)
    assert created["created"] is True
    assert created["primary_key"] == ["id"]
    checked = plugin.validate_primary_keys(
        RelationRef(name="customers_033"),
        expected_keys=["id"],
    )
    assert checked["ok"] is True
    bad = plugin.validate_primary_keys(
        RelationRef(name="customers_033"),
        expected_keys=["name"],
    )
    assert bad["ok"] is False
    assert any(d["code"] == "PMSQL431" for d in bad["diagnostics"])


def test_tier_b_plugin_refuses_engine() -> None:
    plugin = PostgresSqlPlugin(url="mysql+pymysql://localhost/db")
    assert plugin.info.dialect == "mysql"
    assert not plugin.capabilities().supports("transactions")
    with pytest.raises(ValueError, match="Tier"):
        plugin.get_engine()


@pytest.mark.sqlmodel
def test_sqlmodel_pk_helpers() -> None:
    pytest.importorskip("sqlmodel")
    from etlantic_sqlmodel import primary_key_fields, validate_model_primary_keys
    from sqlmodel import Field, SQLModel

    class Order(SQLModel, table=True):
        __tablename__ = "orders_033"
        order_id: int = Field(primary_key=True)
        amount: float

    assert primary_key_fields(Order) == ["order_id"]
    report = validate_model_primary_keys(Order, expected_keys=("order_id",))
    assert report.valid
    bad = validate_model_primary_keys(Order, expected_keys=("amount",))
    assert not bad.valid
