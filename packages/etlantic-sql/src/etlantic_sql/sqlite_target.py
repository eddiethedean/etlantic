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
            f"PRAGMA table_xinfo({_quoted(self.table)})"
        ).fetchall()
        if not rows:
            raise ValueError("SQLite target has no inspectable fields")
        primary_key_rows = [row for row in rows if row[5]]
        try:
            table_list = self.connection.execute("PRAGMA table_list").fetchall()
        except sqlite3.OperationalError:
            table_list = []
        table_entry = next(
            (
                row
                for row in table_list
                if len(row) >= 5 and row[1] == self.table and row[2] == "table"
            ),
            None,
        )
        if table_entry is not None:
            without_rowid = bool(table_entry[4])
        else:
            definition = self.connection.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                (self.table,),
            ).fetchone()
            definition_sql = str(definition[0]) if definition and definition[0] else ""
            without_rowid = (
                definition_sql.lstrip().upper().startswith("CREATE VIRTUAL TABLE")
                or re.search(r"\bWITHOUT\s+ROWID\b", definition_sql, re.IGNORECASE)
                is not None
            )
        primary_key_indexes = self.connection.execute(
            f"PRAGMA index_list({_quoted(self.table)})"
        ).fetchall()
        has_primary_key_index = any(
            (len(index) >= 4 and index[3] == "pk")
            or (
                len(index) < 4
                and isinstance(index[1], str)
                and index[1].startswith("sqlite_autoindex_")
            )
            for index in primary_key_indexes
        )
        rowid_primary_key = (
            len(primary_key_rows) == 1
            and str(primary_key_rows[0][2]).strip().upper() == "INTEGER"
            and not without_rowid
            and not has_primary_key_index
        )
        rowid_primary_key_name = (
            str(primary_key_rows[0][1]) if rowid_primary_key else None
        )
        keys = [row[1] for row in sorted(rows, key=lambda item: item[5]) if row[5]]
        names = [str(row[1]) for row in rows]
        if any(name not in names for name in self.partitions):
            raise ValueError("SQLite target partition field is missing")
        fields: list[dict[str, Any]] = []
        for row in rows:
            _, name, dtype, not_null, default_value, pk, hidden = row
            generated = hidden in {2, 3}
            field_metadata = {
                "has_default": default_value is not None,
                "generated": generated,
                "auto_increment": str(name) == rowid_primary_key_name,
            }
            fields.append(
                {
                    "name": str(name),
                    "type": str(dtype),
                    "required": bool(not_null or pk),
                    "nullable": not bool(not_null or pk),
                    **field_metadata,
                }
            )
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
        target_fields = {field.name: field for field in observation.schema.fields}
        row_fields = set(records[0])
        if any(set(row) != row_fields for row in records):
            raise ValueError(
                "INFER_WRITE_INCOMPATIBLE: SQLite rows must have matching fields"
            )
        if any(
            name not in target_fields
            or target_fields[name].metadata.get("generated") is True
            for name in row_fields
        ):
            raise ValueError(
                "INFER_WRITE_INCOMPATIBLE: SQLite input contains an unknown or generated field"
            )
        columns = [
            field.name
            for field in observation.schema.fields
            if field.name in row_fields
        ]
        target_metadata = observation.metadata
        if mode in {"merge", "upsert"}:
            raw_keys = target_metadata.get("keys")
            raw_key_items = (
                cast(list[Any] | tuple[Any, ...], raw_keys)
                if isinstance(raw_keys, (list, tuple))
                else ()
            )
            keys: list[str] = [key for key in raw_key_items if isinstance(key, str)]
            if (
                not keys
                or len(keys) != len(raw_key_items)
                or not set(keys).issubset(row_fields)
            ):
                raise ValueError(
                    "INFER_WRITE_INCOMPATIBLE: SQLite merge input must contain every key"
                )
        if mode == "partition_replace" and not set(self.partitions).issubset(
            row_fields
        ):
            raise ValueError(
                "INFER_WRITE_INCOMPATIBLE: SQLite partition input must contain every partition field"
            )
        table = _quoted(self.table)
        names = ", ".join(_quoted(column) for column in columns)
        placeholders = ", ".join("?" for _ in columns)
        insert = (
            f"INSERT INTO {table} ({names}) VALUES ({placeholders})"
            if columns
            else f"INSERT INTO {table} DEFAULT VALUES"
        )
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
