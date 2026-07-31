"""Capability vocabulary freeze tests (ADR-015)."""

from __future__ import annotations

from etlantic.connectors.capabilities import (
    CLEANUP,
    CONNECTOR_CAPABILITY_VOCABULARY,
    FORMAT_CSV,
    IDEMPOTENCY,
    LOCAL_FILES_CAPABILITIES,
    PUBLICATION_ATOMIC,
    RECONCILIATION,
    SOURCE_BATCH_SNAPSHOT,
    SOURCE_FILE_GLOB,
    SOURCE_INCREMENTAL_CURSOR,
    SOURCE_PARTITIONED,
    SOURCE_PREDICATE_PUSHDOWN,
    SOURCE_PROJECTION_PUSHDOWN,
    SOURCE_SCHEMA_DISCOVERY,
    SOURCE_STATISTICS_BOUNDED,
    TRANSACTIONS,
    WRITE_APPEND,
    WRITE_MERGE,
    WRITE_OVERWRITE,
    WRITE_PARTITION_REPLACE,
    WRITE_SKIP_IF_EXISTS,
    WRITE_UPSERT,
)


def test_landing_zone_tokens_exact() -> None:
    required = {
        SOURCE_BATCH_SNAPSHOT,
        SOURCE_INCREMENTAL_CURSOR,
        SOURCE_FILE_GLOB,
        FORMAT_CSV,
        IDEMPOTENCY,
        CLEANUP,
    }
    assert required <= CONNECTOR_CAPABILITY_VOCABULARY
    assert required == LOCAL_FILES_CAPABILITIES


def test_extended_vocabulary_spellings() -> None:
    expected = {
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
    assert expected <= CONNECTOR_CAPABILITY_VOCABULARY
    assert SOURCE_BATCH_SNAPSHOT == "source.batch_snapshot"
    assert WRITE_PARTITION_REPLACE == "write.partition_replace"
