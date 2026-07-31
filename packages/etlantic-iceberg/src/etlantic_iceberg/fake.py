"""In-memory Iceberg catalog fake for CI without pyiceberg."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def pyiceberg_available() -> bool:
    try:
        import pyiceberg  # noqa: F401
    except ImportError:
        return False
    return True


@dataclass
class FakeSnapshot:
    snapshot_id: int
    operation: str
    rows: tuple[dict[str, Any], ...]
    parent_id: int | None = None


@dataclass
class FakeTable:
    identifier: str
    schema_fields: tuple[dict[str, Any], ...] = ()
    snapshots: list[FakeSnapshot] = field(default_factory=list)
    current_snapshot_id: int | None = None

    @property
    def current_rows(self) -> tuple[dict[str, Any], ...]:
        if self.current_snapshot_id is None:
            return ()
        for snap in self.snapshots:
            if snap.snapshot_id == self.current_snapshot_id:
                return snap.rows
        return ()


@dataclass
class FakeIcebergCatalog:
    """Stub catalog: snapshot id is the publication identity."""

    tables: dict[str, FakeTable] = field(default_factory=dict)
    _next_snapshot_id: int = 1

    def ensure_table(
        self,
        identifier: str,
        *,
        schema_fields: tuple[dict[str, Any], ...] | None = None,
    ) -> FakeTable:
        table = self.tables.get(identifier)
        if table is None:
            table = FakeTable(
                identifier=identifier,
                schema_fields=schema_fields or (),
            )
            self.tables[identifier] = table
        elif schema_fields and not table.schema_fields:
            table.schema_fields = schema_fields
        return table

    def append(self, identifier: str, rows: list[dict[str, Any]]) -> FakeSnapshot:
        table = self.ensure_table(identifier)
        parent = table.current_snapshot_id
        merged = list(table.current_rows) + list(rows)
        snap = self._new_snapshot("append", tuple(merged), parent=parent)
        table.snapshots.append(snap)
        table.current_snapshot_id = snap.snapshot_id
        return snap

    def overwrite(self, identifier: str, rows: list[dict[str, Any]]) -> FakeSnapshot:
        table = self.ensure_table(identifier)
        parent = table.current_snapshot_id
        snap = self._new_snapshot("overwrite", tuple(rows), parent=parent)
        table.snapshots.append(snap)
        table.current_snapshot_id = snap.snapshot_id
        return snap

    def rollback(self, identifier: str, snapshot_id: int | None) -> None:
        """Discard a staged snapshot that was never current (abort path)."""
        table = self.tables.get(identifier)
        if table is None or snapshot_id is None:
            return
        table.snapshots = [s for s in table.snapshots if s.snapshot_id != snapshot_id]
        if table.current_snapshot_id == snapshot_id:
            table.current_snapshot_id = (
                table.snapshots[-1].snapshot_id if table.snapshots else None
            )

    def get_snapshot(self, identifier: str, snapshot_id: int) -> FakeSnapshot | None:
        table = self.tables.get(identifier)
        if table is None:
            return None
        for snap in table.snapshots:
            if snap.snapshot_id == snapshot_id:
                return snap
        return None

    def _new_snapshot(
        self,
        operation: str,
        rows: tuple[dict[str, Any], ...],
        *,
        parent: int | None,
    ) -> FakeSnapshot:
        snap = FakeSnapshot(
            snapshot_id=self._next_snapshot_id,
            operation=operation,
            rows=rows,
            parent_id=parent,
        )
        self._next_snapshot_id += 1
        return snap


__all__ = ["FakeIcebergCatalog", "FakeSnapshot", "FakeTable", "pyiceberg_available"]
