"""Local storage bindings and domain-neutral storage capability vocabulary."""

from __future__ import annotations

from etlantic.storage.callable_binding import CallableStorage
from etlantic.storage.csv_binding import CsvStorage
from etlantic.storage.delta_capabilities import (
    DELTA_OP_CAPABILITY,
    STORAGE_DELTA_CAPABILITY_EXTRAS,
    STORAGE_DELTA_EXTRA_IMPLIES,
    DeltaStorageOp,
    storage_capability_for_delta_op,
)
from etlantic.storage.json_binding import JsonStorage
from etlantic.storage.memory import MemoryStorage
from etlantic.storage.null import NullStorage
from etlantic.storage.protocol import StorageBinding, as_records, records_to_dicts

__all__ = [
    "DELTA_OP_CAPABILITY",
    "STORAGE_DELTA_CAPABILITY_EXTRAS",
    "STORAGE_DELTA_EXTRA_IMPLIES",
    "CallableStorage",
    "CsvStorage",
    "DeltaStorageOp",
    "JsonStorage",
    "MemoryStorage",
    "NullStorage",
    "StorageBinding",
    "as_records",
    "records_to_dicts",
    "storage_capability_for_delta_op",
]
