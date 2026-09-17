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

    def _serialize(
        self, rows: list[dict[str, Any]], fieldnames: list[str], *, header: bool
    ) -> str:
        output = StringIO(newline="")
        writer = csv.DictWriter(
            output, fieldnames=fieldnames or ["value"], extrasaction="raise"
        )
        if header:
            writer.writeheader()
        writer.writerows(rows)
        return output.getvalue()

    def _append_text(
        self,
        existing_text: str,
        rows: list[dict[str, Any]],
        contract_type: type[Any] | None,
    ) -> str:
        reader = csv.DictReader(StringIO(existing_text, newline=""))
        existing_fieldnames = list(reader.fieldnames or ())
        fieldnames = existing_fieldnames or self._fieldnames(contract_type, rows)
        if not fieldnames:
            fieldnames = ["value"]
        expected = set(fieldnames)
        for row in rows:
            if set(row) != expected:
                raise ValueError(
                    "CSV append rows must match the existing file header exactly"
                )
        appended = self._serialize(rows, fieldnames, header=not existing_fieldnames)
        if not existing_fieldnames:
            return appended
        separator = (
            "" if not existing_text or existing_text.endswith(("\n", "\r")) else "\n"
        )
        return existing_text + separator + appended

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
        policy = (context or {}).get("safe_io")
        if policy is not None:
            from etlantic.io_policy import read_text_safe

            _resolved, text, _events = read_text_safe(
                path,
                policy,
                run_id=str((context or {}).get("run_id") or binding),
                newline="",
            )
            reader = csv.DictReader(StringIO(text, newline=""))
            rows = list(reader)
        else:
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
        policy = (context or {}).get("safe_io")
        if mode == "append" and policy is not None:
            from etlantic.io_policy import read_modify_write_text_safe

            read_modify_write_text_safe(
                path,
                policy,
                lambda existing: self._append_text(existing, rows, contract_type),
                run_id=str((context or {}).get("run_id") or binding),
                newline="",
            )
        elif mode == "append" and path.is_file():
            with path.open("r", newline="", encoding="utf-8") as handle:
                updated = self._append_text(handle.read(), rows, contract_type)
            path.write_text(updated, encoding="utf-8", newline="")
        elif policy is not None:
            from etlantic.io_policy import write_text_safe

            write_text_safe(
                path,
                self._serialize(rows, fieldnames, header=True),
                policy,
                run_id=str((context or {}).get("run_id") or binding),
            )
        else:
            path.write_text(
                self._serialize(rows, fieldnames, header=True),
                encoding="utf-8",
                newline="",
            )
        return {
            "binding": binding,
            "location": str(path),
            "records": len(rows),
            "skipped": False,
        }
