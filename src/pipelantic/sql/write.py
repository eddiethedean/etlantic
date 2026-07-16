"""Write-intent helpers for SQL publication."""

from __future__ import annotations

from typing import Any

from pipelantic.sql.protocol import (
    AtomicPublicationStrategy,
    RelationRef,
    SqlQuery,
    SqlWrite,
    WriteIntentKind,
)


def append(
    target: RelationRef | str,
    source: SqlQuery | RelationRef,
    **metadata: Any,
) -> SqlWrite:
    return SqlWrite(
        intent=WriteIntentKind.APPEND,
        target=_rel(target),
        source=source,
        metadata=metadata,
    )


def insert_select(
    target: RelationRef | str,
    source: SqlQuery | RelationRef,
    **metadata: Any,
) -> SqlWrite:
    return SqlWrite(
        intent=WriteIntentKind.INSERT_SELECT,
        target=_rel(target),
        source=source,
        metadata=metadata,
    )


def replace(
    target: RelationRef | str,
    source: SqlQuery | RelationRef,
    *,
    atomic: AtomicPublicationStrategy = AtomicPublicationStrategy.STAGING_SWAP,
    **metadata: Any,
) -> SqlWrite:
    return SqlWrite(
        intent=WriteIntentKind.REPLACE,
        target=_rel(target),
        source=source,
        atomic=atomic,
        metadata=metadata,
    )


def merge(
    target: RelationRef | str,
    source: SqlQuery | RelationRef,
    *,
    keys: tuple[str, ...],
    **metadata: Any,
) -> SqlWrite:
    return SqlWrite(
        intent=WriteIntentKind.MERGE,
        target=_rel(target),
        source=source,
        merge_keys=keys,
        metadata=metadata,
    )


def _rel(value: RelationRef | str) -> RelationRef:
    return value if isinstance(value, RelationRef) else RelationRef.parse(value)
