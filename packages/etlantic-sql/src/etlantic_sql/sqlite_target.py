"""Real SQLite target inspection and transactional write-mode reference adapter."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from etlantic.inference import check_write_compatibility, infer_records, inspect_target

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _quoted(name: str) -> str:
    if not _IDENTIFIER.fullmatch(name):
        raise ValueError("SQLite target identifiers must be simple SQL names")
    return '"' + name + '"'


@dataclass(slots=True)
class SQLiteTableTarget:
    """Inspect and write one existing table using declared, verified modes.

    The caller owns the connection and supplies a stable public identity.
    Rows stay in the process; only schema, revision, keys, partitions, and
    capabilities enter inference observations and definitions.
    """

    connection: sqlite3.Connection
    table: str
    identity: str
    partitions: tuple[str, ...] = ()
    max_write_rows: int = 10_000

    def __post_init__(self) -> None:
        _quoted(self.table)
        if not self.identity or self.max_write_rows < 1:
            raise ValueError("SQLite target needs an identity and positive row limit")
        if len(set(self.partitions)) != len(self.partitions):
            raise ValueError("SQLite target partitions must be unique")
        for name in self.partitions:
            _quoted(name)

    def exists(self) -> str:
        row = self.connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (self.table,),
        ).fetchone()
        return "present" if row is not None else "absent"

    def inspect_schema(self) -> dict[str, Any]:
        if self.exists() != "present":
            return {"exists": "absent", "identity": self.identity}
        rows = self.connection.execute(
            f"PRAGMA table_info({_quoted(self.table)})"
        ).fetchall()
        if not rows:
            raise ValueError("SQLite target has no inspectable fields")
        keys = [
            name for _, name, _, _, _, pk in sorted(rows, key=lambda row: row[5]) if pk
        ]
        names = [str(row[1]) for row in rows]
        if any(name not in names for name in self.partitions):
            raise ValueError("SQLite target partition field is missing")
        fields = [
            {
                "name": str(name),
                "type": str(dtype),
                "required": True,
                "nullable": not bool(not_null or pk),
            }
            for _, name, dtype, not_null, _, pk in rows
        ]
        modes = ["append", "overwrite"]
        if keys:
            modes.extend(("merge", "upsert"))
        if self.partitions:
            modes.append("partition_replace")
        schema_version = self.connection.execute("PRAGMA schema_version").fetchone()[0]
        data_version = self.connection.execute("PRAGMA data_version").fetchone()[0]
        revision_data = {
            "fields": fields,
            "keys": keys,
            "partitions": self.partitions,
            "schema_version": schema_version,
            "data_version": data_version,
            "local_changes": self.connection.total_changes,
        }
        revision = hashlib.sha256(
            json.dumps(revision_data, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return {
            "exists": "present",
            "identity": self.identity,
            "revision": revision,
            "fields": fields,
            "keys": keys,
            "partitions": list(self.partitions),
            "capabilities": {"write_modes": modes},
        }

    def write_records(
        self,
        records: Sequence[Mapping[str, Any]],
        *,
        mode: str,
        expected_revision: str,
    ) -> int:
        """Apply a checked mode atomically, rejecting schema or mode drift."""
        if not records or len(records) > self.max_write_rows:
            raise ValueError("SQLite write requires a bounded nonempty record batch")
        if self.connection.in_transaction:
            raise ValueError("SQLite target requires an idle transaction")
        observation = inspect_target(self, identity=self.identity)
        if observation.revision != expected_revision or observation.schema is None:
            raise ValueError("INFER_TARGET_STALE: SQLite target revision changed")
        source = infer_records(records, identity="sqlite-write")
        if not source.valid or source.provenance.get("sampled") is True:
            raise ValueError(
                "INFER_WRITE_INCOMPATIBLE: input records are not qualified"
            )
        compatibility = check_write_compatibility(source.schema, observation, mode=mode)
        if not compatibility.compatible or compatibility.casts:
            raise ValueError(
                "INFER_WRITE_INCOMPATIBLE: SQLite write contract is incompatible"
            )
        columns = [field.name for field in observation.schema.fields]
        if any(set(row) != set(columns) for row in records):
            raise ValueError(
                "INFER_WRITE_INCOMPATIBLE: SQLite rows must contain every field"
            )
        table = _quoted(self.table)
        names = ", ".join(_quoted(column) for column in columns)
        placeholders = ", ".join("?" for _ in columns)
        insert = f"INSERT INTO {table} ({names}) VALUES ({placeholders})"
        values = [tuple(row[column] for column in columns) for row in records]
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            if self.inspect_schema()["revision"] != expected_revision:
                raise ValueError("INFER_TARGET_STALE: SQLite target revision changed")
            if mode == "overwrite":
                self.connection.execute(f"DELETE FROM {table}")
            elif mode == "partition_replace":
                predicates = " AND ".join(
                    f"{_quoted(name)} IS ?" for name in self.partitions
                )
                partition_values = {
                    tuple(row[name] for name in self.partitions) for row in records
                }
                for partition in partition_values:
                    self.connection.execute(
                        f"DELETE FROM {table} WHERE {predicates}", partition
                    )
            elif mode in {"merge", "upsert"}:
                raw_keys = observation.metadata.get("keys")
                keys: list[str] = (
                    [str(key) for key in cast(list[Any] | tuple[Any, ...], raw_keys)]
                    if isinstance(raw_keys, (list, tuple))
                    else []
                )
                if not keys:
                    raise ValueError(
                        "INFER_WRITE_INCOMPATIBLE: target keys are missing"
                    )
                nonkeys = [column for column in columns if column not in keys]
                conflict = ", ".join(_quoted(key) for key in keys)
                if nonkeys:
                    assignments = ", ".join(
                        f"{_quoted(column)}=excluded.{_quoted(column)}"
                        for column in nonkeys
                    )
                    insert += f" ON CONFLICT ({conflict}) DO UPDATE SET {assignments}"
                else:
                    insert += f" ON CONFLICT ({conflict}) DO NOTHING"
            self.connection.executemany(insert, values)
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        return len(records)
