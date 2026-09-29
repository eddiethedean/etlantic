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
