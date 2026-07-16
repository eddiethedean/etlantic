"""Local storage bindings for Pipelantic 0.4."""

from __future__ import annotations

from pipelantic.storage.callable_binding import CallableStorage
from pipelantic.storage.csv_binding import CsvStorage
from pipelantic.storage.json_binding import JsonStorage
from pipelantic.storage.memory import MemoryStorage
from pipelantic.storage.null import NullStorage
from pipelantic.storage.protocol import StorageBinding, as_records, records_to_dicts

__all__ = [
    "CallableStorage",
    "CsvStorage",
    "JsonStorage",
    "MemoryStorage",
    "NullStorage",
    "StorageBinding",
    "as_records",
    "records_to_dicts",
]
