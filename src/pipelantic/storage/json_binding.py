"""JSON file storage binding (stdlib)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pipelantic.exceptions import PipelineExecutionError
from pipelantic.storage.protocol import as_records, records_to_dicts


class JsonStorage:
    """Read/write JSON arrays or JSON Lines files."""

    name = "json"

    def __init__(self, *, lines: bool = False) -> None:
        self._lines = lines

    def _path(self, binding: str, location: str | None) -> Path:
        if not location:
            raise PipelineExecutionError(
                f"JSON binding {binding!r} requires a location path",
                code="PMEXEC420",
            )
        return Path(location)

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
                f"JSON source not found: {path}",
                code="PMEXEC421",
            )
        text = path.read_text(encoding="utf-8")
        if self._lines or path.suffix in {".jsonl", ".ndjson"}:
            rows = [json.loads(line) for line in text.splitlines() if line.strip()]
        else:
            payload = json.loads(text) if text.strip() else []
            rows = payload if isinstance(payload, list) else [payload]
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
        if self._lines or path.suffix in {".jsonl", ".ndjson"}:
            path.write_text(
                "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
                encoding="utf-8",
            )
        else:
            path.write_text(
                json.dumps(rows, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        return {"binding": binding, "location": str(path), "records": len(rows)}
