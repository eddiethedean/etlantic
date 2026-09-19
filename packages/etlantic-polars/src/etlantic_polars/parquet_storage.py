"""Read-only, finite local Parquet snapshots for explicit Polars execution.

This adapter does not grant adaptive source authority. A lazy scan is valid only
inside its context manager, including while native work is draining.
"""

from __future__ import annotations

import io
import os
import stat
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl
from anyio.to_thread import run_sync
from pydantic import ValidationError

from etlantic.io_policy import SafeIoPolicy, resolve_under_policy
from etlantic.storage.protocol import as_records
from etlantic.transform.fusion import parquet_source_location

SOURCE_SCHEMA = "etlantic.polars_parquet_source/1"


class SnapshotCleanupError(ValueError):
    """A snapshot owner could not be released; payload and paths stay private."""

    def __init__(self, cleanup_id: str) -> None:
        super().__init__("Bounded Parquet snapshot cleanup failed")
        self.cleanup_id = cleanup_id


@dataclass(frozen=True, slots=True)
class PolarsParquetStorage:
    """Bounded single-file source; no discovery, writes or remote locations.

    Supply ``context['safe_io']`` and a relative ``location``. PyArrow (the
    plugin's ``arrow`` extra) is required for bounded footer inspection.
    """

    max_bytes: int = 64 * 1024 * 1024
    max_rows: int = 100_000
    name: str = "polars-parquet"

    def pending_snapshot_cleanups(self) -> tuple[str, ...]:
        """Compatibility surface: byte snapshots have no disk obligations."""
        return ()

    def reconcile_snapshot_cleanup(self, cleanup_id: str) -> None:
        """Compatibility surface: all tokens are unknown for byte snapshots."""
        del cleanup_id
        raise ValueError("Unknown snapshot cleanup obligation")

    def __post_init__(self) -> None:
        for value, maximum in (
            (self.max_bytes, 256 * 1024 * 1024),
            (self.max_rows, 1_000_000),
        ):
            if type(value) is not int or not 0 < value <= maximum:
                raise ValueError("Invalid bounded Parquet source configuration")
        if self.name != "polars-parquet":
            raise ValueError("Invalid bounded Parquet source identity")

    def configuration(self) -> dict[str, str | int]:
        """Return the closed, static configuration without touching files."""
        return {
            "schema": SOURCE_SCHEMA,
            "max_bytes": self.max_bytes,
            "max_rows": self.max_rows,
        }

    @contextmanager
    def open_scan(
        self, *, location: str | None, context: Mapping[str, Any]
    ) -> Iterator[pl.LazyFrame]:
        """Own a finite immutable snapshot until the caller drains native work.

        Do not return the lazy frame outside this context. There is no shared
        current snapshot, so independent invocations do not share ownership.
        """
        relative = _relative_location(location)
        policy = context.get("safe_io")
        if not isinstance(policy, SafeIoPolicy) or not policy.approved_roots:
            raise ValueError("Bounded Parquet source requires SafeIoPolicy")
        budget = min(self.max_bytes, policy.max_read_bytes)
        if type(budget) is not int or budget <= 0:
            raise ValueError("Invalid bounded Parquet read budget")
        # Resolve under the existing public policy before opening a source.
        root = policy.approved_roots[0]
        resolved, _ = resolve_under_policy(root / relative, policy, must_exist=True)
        with _source_handle(root, relative, resolved) as source:
            before = os.fstat(source)
            if not stat.S_ISREG(before.st_mode) or before.st_size > budget:
                raise ValueError("Parquet source is not a bounded regular file")
            # No artifact is written under an input-writer-accessible parent.
            # The native scan owns immutable bytes, never a reopenable pathname.
            with io.BytesIO() as destination:
                total = 0
                while chunk := os.read(source, min(1024 * 1024, budget - total + 1)):
                    total += len(chunk)
                    if total > budget:
                        raise ValueError("Parquet source exceeds byte budget")
                    destination.write(chunk)
                after = os.fstat(source)
                if (
                    total != before.st_size
                    or before.st_size != after.st_size
                    or before.st_mtime_ns != after.st_mtime_ns
                    or before.st_ctime_ns != after.st_ctime_ns
                ):
                    raise ValueError("Parquet source changed during snapshot")
                snapshot = _sanitize_footer(destination.getvalue(), self.max_rows)
                _inspect_snapshot(snapshot, self.max_rows, budget)
                yield pl.scan_parquet(snapshot, hive_partitioning=False)

    async def read(
        self,
        *,
        binding: str,
        location: str | None,
        contract_type: type[Any] | None,
        context: dict[str, Any],
    ) -> pl.DataFrame:
        """Read and validate independently of adaptive/fused execution."""
        del binding
        # Initialize optional Arrow bindings on the caller thread before native
        # work. Some Arrow builds cannot initialize their extension registry in
        # a freshly created worker. This imports code, never source data.
        from importlib import import_module

        import_module("pyarrow.parquet")

        def collect() -> pl.DataFrame:
            try:
                with self.open_scan(location=location, context=context) as scan:
                    frame = scan.collect()
                    if contract_type is not None:
                        as_records(frame.to_dicts(), contract_type)
                    return frame
            except (
                pl.exceptions.PolarsError,
                pl.exceptions.PanicException,
                ValidationError,
            ):
                raise ValueError(
                    "Bounded Parquet read/contract validation failed"
                ) from None

        # Cancellation waits for native work before releasing snapshot buffers.
        return await run_sync(collect, abandon_on_cancel=False)

    async def write(
        self,
        *,
        binding: str,
        location: str | None,
        data: Any,
        contract_type: type[Any] | None,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Reject all writes before resolving or opening the destination."""
        raise ValueError("Bounded Parquet storage is read-only")


def create_parquet_storage(
    configuration: Mapping[str, Any] | None = None,
) -> PolarsParquetStorage:
    """Create a source from closed static configuration, without file I/O."""
    if configuration is None:
        return PolarsParquetStorage()
    if not isinstance(configuration, Mapping):
        raise ValueError("Invalid bounded Parquet source configuration")
    if (
        set(configuration) != {"schema", "max_bytes", "max_rows"}
        or configuration["schema"] != SOURCE_SCHEMA
    ):
        raise ValueError("Invalid bounded Parquet source configuration")
    return PolarsParquetStorage(
        max_bytes=configuration["max_bytes"], max_rows=configuration["max_rows"]
    )


def _relative_location(location: str | None) -> Path:
    path = parquet_source_location(location)
    return Path(*path.parts)


@contextmanager
def _source_handle(root: Path, relative: Path, resolved: Path) -> Iterator[int]:
    # Descriptor-relative opens fence every component on POSIX, including a
    # symlink replacement between policy resolution and the actual open.
    if os.name == "nt":
        source = os.open(resolved, os.O_RDONLY | os.O_BINARY)
        try:
            if _windows_handle_path(source) != os.path.normcase(str(root / relative)):
                raise ValueError("Parquet source handle escaped its captured location")
            yield source
        finally:
            os.close(source)
        return
    if os.open not in os.supports_dir_fd or not hasattr(os, "O_NOFOLLOW"):
        raise ValueError("Safe Parquet source handles are unavailable on this platform")
    del resolved
    directories: list[int] = []
    source: int | None = None
    try:
        directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        directories.append(os.open(root, directory_flags))
        for component in relative.parts[:-1]:
            directories.append(
                os.open(component, directory_flags, dir_fd=directories[-1])
            )
        source = os.open(
            relative.name,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
            dir_fd=directories[-1],
        )
        yield source
    except OSError:
        raise ValueError("Safe Parquet source open failed") from None
    finally:
        if source is not None:
            os.close(source)
        for directory in reversed(directories):
            os.close(directory)


def _windows_handle_path(descriptor: int) -> str:
    """Check the opened object, not a potentially replaced Windows path."""
    import ctypes
    import msvcrt
    from ctypes import wintypes

    load_library = getattr(ctypes, "WinDLL", None)
    get_os_handle = getattr(msvcrt, "get_osfhandle", None)
    if not callable(load_library) or not callable(get_os_handle):
        raise ValueError("Cannot verify Parquet source handle")
    kernel = load_library("kernel32", use_last_error=True)
    get_path = getattr(kernel, "GetFinalPathNameByHandleW", None)
    if not callable(get_path):
        raise ValueError("Cannot verify Parquet source handle")
    get_path.argtypes = (
        wintypes.HANDLE,
        wintypes.LPWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
    )
    get_path.restype = wintypes.DWORD
    handle = get_os_handle(descriptor)
    size = get_path(handle, None, 0, 0)
    if not isinstance(size, int) or not 0 < size <= 32768:
        raise ValueError("Cannot verify Parquet source handle")
    buffer = ctypes.create_unicode_buffer(size + 1)
    written = get_path(handle, buffer, len(buffer), 0)
    if not isinstance(written, int) or not 0 < written < len(buffer):
        raise ValueError("Cannot verify Parquet source handle")
    path = buffer.value
    if path.startswith("\\\\?\\UNC\\"):
        path = "\\\\" + path[8:]
    elif path.startswith("\\\\?\\"):
        path = path[4:]
    return os.path.normcase(path)


class _CompactFooter:
    """Bounded Compact-Thrift framing only; no schema/object deserialization.

    Parquet FileMetaData field 5 is optional key_value_metadata. Dropping that
    entire field removes ARROW:schema before either Arrow or Rust sees it. All
    other fields retain their exact encoded payload and data-page offsets.
    """

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.offset = 0
        self.steps = 0

    def byte(self) -> int:
        if self.offset >= len(self.data):
            raise ValueError("Invalid bounded Parquet footer")
        value = self.data[self.offset]
        self.offset += 1
        return value

    def varint(self) -> int:
        value = 0
        for shift in range(0, 70, 7):
            byte = self.byte()
            if shift == 63 and byte > 1:
                break
            value |= (byte & 127) << shift
            if not byte & 128:
                return value
        raise ValueError("Invalid bounded Parquet footer integer")

    def integer(self) -> int:
        value = self.varint()
        return (value >> 1) ^ -(value & 1)

    def advance(self, size: int) -> None:
        if size < 0 or size > len(self.data) - self.offset:
            raise ValueError("Invalid bounded Parquet footer size")
        self.offset += size

    def header(self, previous: int) -> tuple[int, int]:
        header = self.byte()
        if header == 0:
            return 0, 0
        kind = header & 15
        delta = header >> 4
        number = previous + delta if delta else self.integer()
        if not 0 < number <= 32767 or not 1 <= kind <= 12:
            raise ValueError("Invalid bounded Parquet footer field")
        return number, kind

    def skip(self, kind: int, depth: int = 0, *, collection: bool = False) -> None:
        self.steps += 1
        if depth > 32 or self.steps > len(self.data):
            raise ValueError("Parquet footer exceeds parsing bounds")
        if kind in (1, 2):
            if collection and self.byte() not in (1, 2):
                raise ValueError("Invalid bounded Parquet footer boolean")
        elif kind == 3:
            self.advance(1)
        elif kind in (4, 5, 6):
            self.varint()
        elif kind == 7:
            self.advance(8)
        elif kind == 8:
            self.advance(self.varint())
        elif kind in (9, 10):
            header = self.byte()
            count = header >> 4
            count = self.varint() if count == 15 else count
            item = header & 15
            if count > len(self.data) - self.offset or not 1 <= item <= 12:
                raise ValueError("Invalid bounded Parquet footer collection")
            for _ in range(count):
                self.skip(item, depth + 1, collection=True)
        elif kind == 11:
            count = self.varint()
            if count > (len(self.data) - self.offset) // 2:
                raise ValueError("Invalid bounded Parquet footer map")
            if count:
                header = self.byte()
                for _ in range(count):
                    self.skip(header >> 4, depth + 1, collection=True)
                    self.skip(header & 15, depth + 1, collection=True)
        elif kind == 12:
            previous = 0
            while True:
                number, item = self.header(previous)
                if not item:
                    break
                self.skip(item, depth + 1)
                previous = number
        else:
            raise ValueError("Invalid bounded Parquet footer type")


def _sanitize_footer(snapshot: bytes, max_rows: int) -> bytes:
    """Strip optional metadata using bounded framing before any native reader."""
    if len(snapshot) < 12 or snapshot[:4] != b"PAR1" or snapshot[-4:] != b"PAR1":
        raise ValueError("Invalid bounded Parquet source")
    size = int.from_bytes(snapshot[-8:-4], "little")
    if not 0 < size <= len(snapshot) - 12:
        raise ValueError("Invalid bounded Parquet footer size")
    start = len(snapshot) - 8 - size
    parser = _CompactFooter(snapshot[start:-8])
    result = bytearray()
    previous = 0
    emitted = 0
    seen: set[int] = set()
    while True:
        number, kind = parser.header(previous)
        if not kind:
            break
        if number in seen:
            raise ValueError("Duplicate bounded Parquet footer field")
        seen.add(number)
        payload = parser.offset
        if number == 3:
            if kind != 6 or not 0 <= parser.integer() <= max_rows:
                raise ValueError("Parquet source exceeds schema or row bounds")
        else:
            parser.skip(kind)
        if number != 5:
            # Recompute delta headers after field 5 is removed.
            delta = number - emitted
            if 0 < delta <= 15:
                result.append((delta << 4) | kind)
            else:
                result.append(kind)
                encoded = number << 1
                while encoded >= 128:
                    result.append((encoded & 127) | 128)
                    encoded >>= 7
                result.append(encoded)
            result.extend(parser.data[payload : parser.offset])
            emitted = number
        previous = number
    if parser.offset != len(parser.data) or not {1, 2, 3, 4} <= seen:
        raise ValueError("Invalid bounded Parquet footer")
    result.append(0)
    return snapshot[:start] + result + len(result).to_bytes(4, "little") + b"PAR1"


def _inspect_snapshot(snapshot: bytes, max_rows: int, budget: int) -> None:
    # Inspect all source columns, not merely columns surviving projection.
    import pyarrow as pa
    import pyarrow.parquet as pq

    try:
        with pq.ParquetFile(
            pa.BufferReader(snapshot),
            pre_buffer=False,
            thrift_string_size_limit=budget,
            thrift_container_size_limit=budget,
        ) as parquet:
            metadata = parquet.metadata
            # Inspect physical Parquet fields. Converting ARROW:schema metadata
            # to an Arrow schema can invoke registered extension deserializers
            # on attacker-controlled metadata, before the primitive type gate.
            schema = parquet.schema
            if metadata.num_rows > max_rows or not 0 < len(schema) <= 8:
                raise ValueError("Parquet source exceeds schema or row bounds")
            if len(set(schema.names)) != len(schema) or any(
                schema.column(index).physical_type not in {"INT64", "BOOLEAN"}
                or str(schema.column(index).logical_type)
                not in {
                    "None",
                    "Int(bitWidth=64, isSigned=true)",
                }
                or schema.column(index).path != schema.column(index).name
                or schema.column(index).max_repetition_level != 0
                for index in range(len(schema))
            ):
                raise ValueError(
                    "Parquet source requires primitive int64/boolean columns"
                )
            total = 0
            for group_index in range(metadata.num_row_groups):
                group = metadata.row_group(group_index)
                for column_index in range(group.num_columns):
                    size = group.column(column_index).total_uncompressed_size
                    if size < 0:
                        raise ValueError("Invalid Parquet source metadata")
                    total += size
                    if total > budget:
                        raise ValueError("Parquet source exceeds decoded byte budget")
    except (pa.ArrowException, OSError):
        raise ValueError("Invalid bounded Parquet source") from None


__all__ = ["PolarsParquetStorage", "create_parquet_storage"]
