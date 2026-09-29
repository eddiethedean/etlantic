"""Provider-backed write-mode evidence against a real SQLite transaction."""

from __future__ import annotations

import sqlite3

import pytest

import etlantic as etl


def test_sqlite_target_executes_all_declared_write_modes() -> None:
    sql = pytest.importorskip("etlantic_sql")
    connection = sqlite3.connect(":memory:")
    connection.execute(
        "CREATE TABLE orders (id INTEGER PRIMARY KEY, amount INTEGER NOT NULL, part TEXT NOT NULL)"
    )
    connection.commit()
    target = sql.SQLiteTableTarget(
        connection, "orders", "orders-test", partitions=("part",)
    )
    expected = [
        ("append", {"id": 1, "amount": 2, "part": "a"}, [(1, 2, "a")]),
        ("overwrite", {"id": 2, "amount": 3, "part": "b"}, [(2, 3, "b")]),
        ("merge", {"id": 2, "amount": 4, "part": "b"}, [(2, 4, "b")]),
        (
            "upsert",
            {"id": 3, "amount": 5, "part": "b"},
            [(2, 4, "b"), (3, 5, "b")],
        ),
        (
            "partition_replace",
            {"id": 4, "amount": 6, "part": "b"},
            [(4, 6, "b")],
        ),
    ]
    for mode, record, rows in expected:
        observation = etl.inspect_target(target)
        assert observation.exists == "present"
        assert observation.revision
        assert mode in observation.metadata["capabilities"]["write_modes"]
        compatibility = etl.check_write_compatibility(
            etl.infer_records([record]).schema, observation, mode=mode
        )
        assert compatibility.compatible
        dataset = etl.from_records_for_target(
            [record], target, name=f"orders_{mode}", write_mode=mode
        )
        assert dataset.definition().nodes[-1].bindings["target"]["write_mode"] == mode
        assert (
            target.write_records(
                [record], mode=mode, expected_revision=observation.revision
            )
            == 1
        )
        assert connection.execute("SELECT * FROM orders ORDER BY id").fetchall() == rows

    stale = etl.inspect_target(target).revision
    connection.execute("UPDATE orders SET amount=7 WHERE id=4")
    connection.commit()
    with pytest.raises(ValueError, match="INFER_TARGET_STALE"):
        target.write_records(
            [{"id": 5, "amount": 8, "part": "b"}],
            mode="append",
            expected_revision=stale,
        )
    assert connection.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 1


def test_sqlite_target_allows_omitted_defaulted_columns() -> None:
    sql = pytest.importorskip("etlantic_sql")
    connection = sqlite3.connect(":memory:")
    connection.execute(
        "CREATE TABLE events (id INTEGER PRIMARY KEY, value TEXT NOT NULL, "
        "created_at TEXT NOT NULL DEFAULT 'PRIVATE_DEFAULT_VALUE_99')"
    )
    connection.commit()
    target = sql.SQLiteTableTarget(connection, "events", "events-test")

    observation = etl.inspect_target(target)
    assert observation.schema is not None
    created_at = next(
        field for field in observation.schema.fields if field.name == "created_at"
    )
    assert created_at.metadata["has_default"] is True
    assert "PRIVATE_DEFAULT_VALUE_99" not in str(observation.to_dict())
    compatibility = etl.check_write_compatibility(
        etl.infer_records([{"id": 1, "value": "ok"}]).schema,
        observation,
    )
    assert compatibility.compatible

    assert (
        target.write_records(
            [{"id": 1, "value": "ok"}],
            mode="append",
            expected_revision=observation.revision,
        )
        == 1
    )
    assert connection.execute(
        "SELECT id, value, created_at FROM events"
    ).fetchone() == (1, "ok", "PRIVATE_DEFAULT_VALUE_99")


def test_sqlite_target_recognizes_omitted_rowid_primary_key() -> None:
    sql = pytest.importorskip("etlantic_sql")
    connection = sqlite3.connect(":memory:")
    connection.execute(
        "CREATE TABLE events (id INTEGER PRIMARY KEY, value TEXT NOT NULL)"
    )
    connection.commit()
    target = sql.SQLiteTableTarget(connection, "events", "events-rowid-test")

    observation = etl.inspect_target(target)
    assert observation.schema is not None
    id_field = next(field for field in observation.schema.fields if field.name == "id")
    assert id_field.metadata["auto_increment"] is True
    compatibility = etl.check_write_compatibility(
        etl.infer_records([{"value": "ok"}]).schema,
        observation,
    )
    assert compatibility.compatible

    assert (
        target.write_records(
            [{"value": "ok"}],
            mode="append",
            expected_revision=observation.revision,
        )
        == 1
    )
    assert connection.execute("SELECT id, value FROM events").fetchone() == (1, "ok")


def test_sqlite_target_does_not_mark_non_rowid_primary_keys_as_generated() -> None:
    sql = pytest.importorskip("etlantic_sql")
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE int_key (id INT PRIMARY KEY, value TEXT NOT NULL)")
    connection.execute(
        "CREATE TABLE no_rowid (id INTEGER PRIMARY KEY, value TEXT NOT NULL) WITHOUT ROWID"
    )
    connection.execute(
        "CREATE TABLE desc_key (id INTEGER PRIMARY KEY DESC, value TEXT NOT NULL)"
    )
    connection.commit()

    for table in ("int_key", "no_rowid", "desc_key"):
        observation = etl.inspect_target(
            sql.SQLiteTableTarget(connection, table, f"{table}-test")
        )
        assert observation.schema is not None
        id_field = next(
            field for field in observation.schema.fields if field.name == "id"
        )
        assert id_field.metadata["auto_increment"] is False
