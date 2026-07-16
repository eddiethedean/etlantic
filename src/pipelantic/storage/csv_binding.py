"""CSV file storage binding (stdlib)."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from pipelantic.exceptions import PipelineExecutionError
from pipelantic.storage.protocol import as_records, records_to_dicts


class CsvStorage:
    """Read/write CSV files using ContractModel field order when available."""

    name = "csv"

    def _path(self, binding: str, location: str | None) -> Path:
        if not location:
            raise PipelineExecutionError(
                f"CSV binding {binding!r} requires a location path",
                code="PMEXEC430",
            )
        return Path(location)

    def _fieldnames(
        self, contract_type: type[Any] | None, rows: list[dict[str, Any]]
    ) -> list[str]:
        if contract_type is not None and hasattr(contract_type, "model_fields"):
            return list(contract_type.model_fields.keys())
        if rows:
            return list(rows[0].keys())
        return []

    async def read(
        self,
        *,
        binding: str,
        location: str | None,
        contract_type: type[Any] | None,
        context: dict[str, Any],
    ) -> Any:
        path = self._path(binding, location)
        if not path.is_file():
            raise PipelineExecutionError(
                f"CSV source not found: {path}",
                code="PMEXEC431",
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
        path = self._path(binding, location)
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = records_to_dicts(as_records(data, contract_type))
        fieldnames = self._fieldnames(contract_type, rows)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames or ["value"])
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        return {"binding": binding, "location": str(path), "records": len(rows)}
