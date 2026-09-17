"""CSV file storage binding (stdlib)."""

from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
from typing import Any

from etlantic.exceptions import PipelineExecutionError
from etlantic.storage.protocol import as_records, records_to_dicts

_UNSUPPORTED_WRITE_MODES = frozenset({"merge", "upsert"})


class CsvStorage:
    """Read/write CSV files using ContractModel field order when available."""

    name = "csv"

    def _path(
        self, binding: str, location: str | None, context: dict[str, Any] | None
    ) -> Path:
        if not location:
            raise PipelineExecutionError(
                f"CSV binding {binding!r} requires a location path",
                code="PMEXEC453",
            )
        raw = Path(location)
        policy = (context or {}).get("safe_io")
        if policy is not None:
            from etlantic.io_policy import resolve_under_policy

            resolved, _events = resolve_under_policy(
                raw, policy, run_id=str((context or {}).get("run_id") or "csv")
            )
            return Path(resolved)
        return raw

    def _fieldnames(
        self, contract_type: type[Any] | None, rows: list[dict[str, Any]]
    ) -> list[str]:
        if contract_type is not None and hasattr(contract_type, "model_fields"):
            return list(contract_type.model_fields.keys())
        if rows:
            return list(rows[0].keys())
        return []

    def _append_fieldnames(
        self,
        path: Path,
        contract_type: type[Any] | None,
        rows: list[dict[str, Any]],
    ) -> list[str]:
        """Use the existing header as the append serialization authority."""
        with path.open(newline="", encoding="utf-8") as handle:
            existing = csv.DictReader(handle)
            fieldnames = list(existing.fieldnames or ())
        if not fieldnames:
            return self._fieldnames(contract_type, rows)
        expected = set(fieldnames)
        for row in rows:
            if set(row) != expected:
                raise ValueError(
                    "CSV append rows must match the existing file header exactly"
                )
        return fieldnames

    async def read(
        self,
        *,
        binding: str,
        location: str | None,
        contract_type: type[Any] | None,
        context: dict[str, Any],
    ) -> Any:
        path = self._path(binding, location, context)
        if not path.is_file():
            raise PipelineExecutionError(
                f"CSV source not found: {path}",
                code="PMEXEC454",
            )
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
        # Coerce numeric-looking ints when contract fields are int.
        if contract_type is not None and hasattr(contract_type, "model_fields"):
            coerced: list[dict[str, Any]] = []
            for row in rows:
                item: dict[str, Any] = {}
                for key, value in row.items():
                    field = contract_type.model_fields.get(key)
                    ann = getattr(field, "annotation", None) if field else None
                    if ann is int and value not in (None, ""):
                        item[key] = int(value)
                    elif ann is float and value not in (None, ""):
                        item[key] = float(value)
                    else:
                        item[key] = value
                coerced.append(item)
            rows = coerced
        return as_records(rows, contract_type)

    async def write(
        self,
        *,
        binding: str,
        location: str | None,
        data: Any,
        contract_type: type[Any] | None,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        mode = str((context or {}).get("write_mode") or "overwrite").lower()
        if mode in _UNSUPPORTED_WRITE_MODES:
            raise PipelineExecutionError(
                f"CSV binding {binding!r} does not support write_mode={mode!r}; "
                "failing closed.",
                code="PMEXEC455",
            )
        path = self._path(binding, location, context)
        rows = records_to_dicts(as_records(data, contract_type))
        fieldnames = self._fieldnames(contract_type, rows)
        if mode in {"skip_if_exists", "skip"} and path.is_file():
            return {
                "binding": binding,
                "location": str(path),
                "records": 0,
                "skipped": True,
            }
        path.parent.mkdir(parents=True, exist_ok=True)
        if mode == "append" and path.is_file():
            empty_file = path.stat().st_size == 0
            fieldnames = self._append_fieldnames(path, contract_type, rows)
            # Validate the complete batch before opening the destination for
            # append, so a malformed row cannot leave a partial write.
            output = StringIO(newline="")
            writer = csv.DictWriter(
                output, fieldnames=fieldnames or ["value"], extrasaction="raise"
            )
            if empty_file:
                writer.writeheader()
            writer.writerows(rows)
            with path.open("a", newline="", encoding="utf-8") as handle:
                handle.write(output.getvalue())
        else:
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames or ["value"])
                writer.writeheader()
                for row in rows:
                    writer.writerow(row)
        return {
            "binding": binding,
            "location": str(path),
            "records": len(rows),
            "skipped": False,
        }
