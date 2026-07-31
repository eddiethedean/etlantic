"""Frozen connector capability vocabulary (ADR-015)."""

from __future__ import annotations

# Landing-zone / local source (required tokens)
SOURCE_BATCH_SNAPSHOT = "source.batch_snapshot"
SOURCE_INCREMENTAL_CURSOR = "source.incremental_cursor"
SOURCE_FILE_GLOB = "source.file_glob"
FORMAT_CSV = "format.csv"
IDEMPOTENCY = "idempotency"
CLEANUP = "cleanup"

# Extended connector vocabulary
SOURCE_PARTITIONED = "source.partitioned"
SOURCE_PREDICATE_PUSHDOWN = "source.predicate_pushdown"
SOURCE_PROJECTION_PUSHDOWN = "source.projection_pushdown"
SOURCE_SCHEMA_DISCOVERY = "source.schema_discovery"
SOURCE_STATISTICS_BOUNDED = "source.statistics_bounded"

WRITE_APPEND = "write.append"
WRITE_OVERWRITE = "write.overwrite"
WRITE_MERGE = "write.merge"
WRITE_UPSERT = "write.upsert"
WRITE_SKIP_IF_EXISTS = "write.skip_if_exists"
WRITE_PARTITION_REPLACE = "write.partition_replace"

PUBLICATION_ATOMIC = "publication.atomic"
TRANSACTIONS = "transactions"
RECONCILIATION = "reconciliation"

CONNECTOR_CAPABILITY_VOCABULARY: frozenset[str] = frozenset(
    {
        SOURCE_BATCH_SNAPSHOT,
        SOURCE_INCREMENTAL_CURSOR,
        SOURCE_FILE_GLOB,
        FORMAT_CSV,
        IDEMPOTENCY,
        CLEANUP,
        SOURCE_PARTITIONED,
        SOURCE_PREDICATE_PUSHDOWN,
        SOURCE_PROJECTION_PUSHDOWN,
        SOURCE_SCHEMA_DISCOVERY,
        SOURCE_STATISTICS_BOUNDED,
        WRITE_APPEND,
        WRITE_OVERWRITE,
        WRITE_MERGE,
        WRITE_UPSERT,
        WRITE_SKIP_IF_EXISTS,
        WRITE_PARTITION_REPLACE,
        PUBLICATION_ATOMIC,
        TRANSACTIONS,
        RECONCILIATION,
    }
)

LOCAL_FILES_CAPABILITIES: frozenset[str] = frozenset(
    {
        SOURCE_BATCH_SNAPSHOT,
        SOURCE_INCREMENTAL_CURSOR,
        SOURCE_FILE_GLOB,
        FORMAT_CSV,
        IDEMPOTENCY,
        CLEANUP,
    }
)

__all__ = [
    "CLEANUP",
    "CONNECTOR_CAPABILITY_VOCABULARY",
    "FORMAT_CSV",
    "IDEMPOTENCY",
    "LOCAL_FILES_CAPABILITIES",
    "PUBLICATION_ATOMIC",
    "RECONCILIATION",
    "SOURCE_BATCH_SNAPSHOT",
    "SOURCE_FILE_GLOB",
    "SOURCE_INCREMENTAL_CURSOR",
    "SOURCE_PARTITIONED",
    "SOURCE_PREDICATE_PUSHDOWN",
    "SOURCE_PROJECTION_PUSHDOWN",
    "SOURCE_SCHEMA_DISCOVERY",
    "SOURCE_STATISTICS_BOUNDED",
    "TRANSACTIONS",
    "WRITE_APPEND",
    "WRITE_MERGE",
    "WRITE_OVERWRITE",
    "WRITE_PARTITION_REPLACE",
    "WRITE_SKIP_IF_EXISTS",
    "WRITE_UPSERT",
]
