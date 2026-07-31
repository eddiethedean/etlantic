"""In-memory Snowflake fake: autocommit-off + query_id evidence."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


def snowflake_sdk_available() -> bool:
    try:
        import snowflake.connector  # noqa: F401
    except ImportError:
        return False
    return True


@dataclass
class FakeQueryResult:
    query_id: str
    rows_affected: int = 0
    rows: tuple[dict[str, Any], ...] = ()


@dataclass
class FakeSnowflakeConnection:
    """Transactional fake: autocommit is always off.

    Staged DML lives in a transaction buffer until ``commit()`` or ``rollback()``.
    Every statement receives a stable ``query_id`` for CommitReceipt evidence and
    post-loss reconciliation.
    """

    autocommit: bool = False
    tables: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    _txn: list[tuple[str, str, list[dict[str, Any]]]] = field(default_factory=list)
    _committed_queries: dict[str, FakeQueryResult] = field(default_factory=dict)
    _pending_queries: dict[str, FakeQueryResult] = field(default_factory=dict)
    _query_seq: int = 0

    def __post_init__(self) -> None:
        # Enforce transactional path regardless of constructor override.
        self.autocommit = False

    def execute(
        self,
        sql: str,
        *,
        table: str,
        rows: list[dict[str, Any]] | None = None,
        operation: str = "append",
    ) -> FakeQueryResult:
        if self.autocommit:
            raise RuntimeError("autocommit must remain False for transactional path")
        self._query_seq += 1
        query_id = f"sfqid-{self._query_seq:08d}-{uuid.uuid4().hex[:6]}"
        payload = list(rows or [])
        result = FakeQueryResult(query_id=query_id, rows_affected=len(payload), rows=())
        self._txn.append((operation, table, payload))
        self._pending_queries[query_id] = result
        return result

    def select(self, table: str) -> FakeQueryResult:
        self._query_seq += 1
        query_id = f"sfqid-{self._query_seq:08d}-{uuid.uuid4().hex[:6]}"
        rows = tuple(self.tables.get(table, []))
        result = FakeQueryResult(query_id=query_id, rows_affected=0, rows=rows)
        self._committed_queries[query_id] = result
        return result

    def commit(self) -> list[str]:
        query_ids: list[str] = []
        for operation, table, rows in self._txn:
            current = list(self.tables.get(table, []))
            if operation in {"overwrite", "replace"}:
                current = list(rows)
            elif operation == "merge":
                # Keyed upsert on "id" when present; else append.
                by_id = {
                    r["id"]: dict(r)
                    for r in current
                    if isinstance(r, dict) and "id" in r
                }
                rest = [r for r in current if not (isinstance(r, dict) and "id" in r)]
                for row in rows:
                    if isinstance(row, dict) and "id" in row:
                        by_id[row["id"]] = dict(row)
                    else:
                        rest.append(
                            dict(row) if isinstance(row, dict) else {"value": row}
                        )
                current = rest + list(by_id.values())
            else:
                current.extend(rows)
            self.tables[table] = current
        query_ids = list(self._pending_queries)
        self._committed_queries.update(self._pending_queries)
        self._pending_queries.clear()
        self._txn.clear()
        return query_ids

    def rollback(self) -> None:
        self._txn.clear()
        self._pending_queries.clear()

    def lookup_query(self, query_id: str) -> FakeQueryResult | None:
        return self._committed_queries.get(query_id) or self._pending_queries.get(
            query_id
        )


__all__ = [
    "FakeQueryResult",
    "FakeSnowflakeConnection",
    "snowflake_sdk_available",
]
